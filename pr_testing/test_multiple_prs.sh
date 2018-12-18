#!/bin/bash -ex
# This script will be called by Jenkins job ( TODO what job)
# and
# 1) will merge multiple PRs for multiple repos
# 2) run tests and post result on github
# ---
# Constants
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
# WORKSPACE=$(dirname ${CMS_BOT_DIR} )  # TODO use jenkins variable

CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
BUILD_DIR="testBuildDir"  # Where pkgtools/cmsBuild builds software
# ---

## TODO check if the variable there
# Input variable
PULL_REQUESTS=$PULL_REQUESTS              # "cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116"
RELEASE_FORMAT=$RELEASE_FORMAT             # CMS SW TAG found in config_map.py
# PULL_REQUEST=$PULL_REQUEST              # CMSSW PR number, should avoid
# CMSDIST_PR=$CMSDIST_PR                  # CMSDIST PR number, should avoid
ARCHITECTURE=$ARCHITECTURE               # architecture (ex. slc6_amd64_gcc700)
# RELEASE_FORMAT=           # RELEASE_QUEUE found in config_map.py (ex. CMSSW_10_4_ROOT6_X )
# DO_TESTS=
# DO_SHORT_MATRIX=
# DO_STATIC_CHECKS=
# DO_DUPLICATE_CHECKS=
# MATRIX_EXTRAS=
# ADDITIONAL_PULL_REQUESTS=$ADDITIONAL_PULL_REQUESTS   # aditonal CMSSW PRs
# WORKFLOWS_FOR_VALGRIND_TEST=
AUTO_POST_MESSAGE=$AUTO_POST_MESSAGE
RUN_CONFIG_VIEWER=${RUN_CONFIG_VIEWER}
USE_DAS_CACHE=${USE_DAS_CACHE}
BRANCH_NAME=${BRANCH_NAME}
APPLY_FIREWORKS_RULE=${APPLY_FIREWORKS_RULE}
RUN_IGPROF=${RUN_IGPROF}
TEST_CLANG_COMPILATION=${TEST_CLANG_COMPILATION}
MATRIX_TIMEOUT=${MATRIX_TIMEOUT}
EXTRA_MATRIX_ARGS=${EXTRA_MATRIX_ARGS}
DO_ADDON_TESTS=${DO_ADDON_TESTS}
RUN_ON_SLAVE=${RUN_ON_SLAVE}
FULL_TOOLCONF=${FULL_TOOLCONF}
COMPARISON_ARCH=${COMPARISON_ARCH}
DISABLE_POISON=${DISABLE_POISON}
JENKINS_URL=${JENKINS_URL}

WORKSPACE=${WORKSPACE}
# USER=${USER}
BUILD_NUMBER=${BUILD_NUMBER}
JOB_NAME=${JOB_NAME}
# TODO delete after

source ${PR_TESTING_DIR}/_helper_functions.sh   # general helper functions

# Functions unique to script
function modify_comment_all_prs() {
    # modify all PR's with message that job has been triggered and add a link to jobs console
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        ${CMS_BOT_DIR}/modify_comment.py -r ${PR_NAME_AND_REPO} -t JENKINS_TEST_URL \
            -m "https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console Started: $(date '+%Y/%m/%d %H:%M')" ${PR_NR} ${DRY_RUN} || true
    done
}

function report-pull-request-results_all_prs() {
    # post message of test status on Github on all PR's
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        ${CMS_BOT_DIR}/report-pull-request-results $@ --repo ${PR_NAME_AND_REPO} --pr ${PR_NR}  # $@ - pass all parameters given to function
    done
}

function report-pull-request-results_all_prs_with_commit() {
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        LAST_PR_COMMIT=$(cat $(get_path_to_pr_metadata ${PR})/COMMIT) # get cashed commit hash
        ${CMS_BOT_DIR}/report-pull-request-results $@ --repo ${PR_NAME_AND_REPO} --pr ${PR_NR} -c ${LAST_PR_COMMIT}
    done
}

# ----------
# -- MAIN --
# ----------
echo_section "Variable setup"

DRY_RUN=
if [ "X$AUTO_POST_MESSAGE" != Xtrue ]; then
  DRY_RUN='--no-post'
fi
CMSSW_CYCLE=$(echo ${RELEASE_FORMAT} | sed 's/_X.*/_X/')  # RELEASE_FORMAT - CMSSW_10_4_X_2018-11-26-2300
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | sed 's/ //g' | tr ',' ' ')  # to make consistent separation in list
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )  # Repos without pull number
fail_if_empty "${UNIQ_REPOS}" "UNIQ_REPOS"
UNIQ_REPO_NAMES=$(echo ${UNIQ_REPOS} | tr ' ' '\n' | sed 's|.*/||' )
UNIQ_REPO_NAMES_WITH_COUNT=$(echo ${UNIQ_REPO_NAMES} | sort | uniq -c )

CMS_WEEKLY_REPO=cms.week$(echo $(tail -1 $CMS_BOT_DIR/ib-weeks | sed 's|.*-||') % 2 | bc)
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${PUB_USER}" = X ] ; then export PUB_USER="cms-sw" ; fi  # TODO-export PUB_USER should be avoided ?

ls /cvmfs/cms.cern.ch
which scram 2>/dev/null || source /cvmfs/cms.cern.ch/cmsset_default.sh

echo_section "Pull request checks"
# Check if same organization/repo PRs
if [ $(echo ${UNIQ_REPO_NAMES_WITH_COUNT}  | grep -v '1 ' | wc -w ) -gt 0 ]; then
    >&2 echo "ERROR: multiple PRs from different organisations but same repos:"
    >$2 echo ${UNIQ_REPO_NAMES_WITH_COUNT}
    exit 1
fi

# Filter PR for specific repo and then check if its PRs point to same base branch
for U_REPO in ${UNIQ_REPOS}; do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ' )
    MASTER_LIST=""
    for PR in ${FILTERED_PRS}; do
        MASTER_LIST="${MASTER_LIST} $(get_base_branch ${PR})"
    done
    UNIQ_MASTERS=$(echo ${MASTER_LIST} | tr ' ' '\n' | sort | uniq )
    if [ -z ${UNIQ_MASTERS} ]; then continue ; fi
    NUMBER_U_M=$(echo ${UNIQ_MASTERS} | wc -l )
    if  [ ! ${NUMBER_U_M}  -eq 1 ]; then
        >&2 echo "ERROR: PRs for  repo '${U_REPO}' wants to merge to different branches: ${UNIQ_MASTERS}"
        exit 1
    fi
done

# If CMSSW_CYCLE is not set, get it from CMSSW or CMSDIST. Else, fail.
if [ -z ${CMSSW_CYCLE} ]; then
     CMSDIST_PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep '/cmsdist#' | head -n 1) # get 1st one
     CMSSW_PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep '/cmssw#' | head -n 1)
     if [ ! -z ${CMSDIST_PR} ] ; then
        PR_METADATA_PATH=$(get_cached_GH_JSON "${CMSDIST_PR}")
        # CMSSW branch name is release cycle
        CMSSW_CYCLE=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
     elif [[ ! -z ${CMSSW_PR} && -z ${CMSSW_CYCLE} ]] ; then
        CMSSW_METADATA_PATH=$(get_cached_GH_JSON "${CMSSW_PR}")
        SW_BASE_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
        CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "" "${SW_BASE_BRANCH}" "${ARCHITECTURE}")
        CMSSW_CYCLE=$(echo ${CONFIG_LINE} | sed 's/^.*RELEASE_QUEUE=//' | sed 's/;.*//' )
     fi
fi

fail_if_empty "${CMSSW_CYCLE}" "CMSSW release cycle unsent and could not be determined."
if [ -z ${CONFIG_LINE} ] ; then  # Get config line
    CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "${CMSSW_CYCLE}" "" "${ARCHITECTURE}" )
fi

if [ -z ${ARCHITECTURE} ] ; then
    ARCHITECTURE=$(echo ${CONFIG_LINE} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )
fi
export SCRAM_ARCH=${ARCHITECTURE}

CMSSW_IB=  # We are getting CMSSW_IB, so that we wont rebuild all the software
for relpath in $(scram -a $ARCHITECTURE l -c $CMSSW_CYCLE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests"  | awk '{print $2":"$3}' | sort -r | sed 's|^.*:||') ; do
  [ -e $relpath/build-errors ] && continue
  CMSSW_IB=$(basename $relpath)
  break
done
[ "X$CMSSW_IB" = "X" ] && CMSSW_IB=$(scram -a $ARCHITECTURE l -c ${CMSSW_CYCLE} | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | tail -n 1)

PKG_TOOL_BRANCH=$(echo ${CONFIG_LINE} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )
PKG_TOOL_VERSION=$(echo ${PKG_TOOL_BRANCH} | cut -d- -f 2)
if [[ ${PKG_TOOL_VERSION} -lt 32 && ! -z $(echo ${UNIQ_REPO_NAMES} | tr ' ' '\n' | grep -v -w cmssw | grep -v -w cmsdist ) ]] ; then
    # If low version and but there are external repos to test, fail
    >&2 echo "ERROR: RELEASE_FORMAT ${RELEASE_FORMAT} uses PKG_TOOL_BRANCH ${PKG_TOOL_BRANCH} which is lower then required to test externals."
    exit 1
fi

# Do git pull --rebase for each PR except for /cmssw
for U_REPO in $(echo ${UNIQ_REPOS} | tr ' ' '\n'  | grep -v '/cmssw' ); do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        git_clone_and_merge "$(get_cached_GH_JSON "${PR}")"
    done
done

# Preparations depending on from repo type
CMSSW_ORG=
BUILD_EXTERNAL=false
for U_REPO in ${UNIQ_REPOS}; do
    PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
    PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
    case "$PKG_NAME" in  # We do not care where the repo is kept (ex. cmssw organisation or other)
		cmssw)
            CMSSW_ORG=$(echo ${PKG_REPO} | sed 's|/.*||')
		;;
		cmsdist)
		    BUILD_EXTERNAL=true
		;;
		*)
			PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
			PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
			${PR_TESTING_DIR}/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$PKG_NAME" "$CMSSW_CYCLE" "$ARCHITECTURE"
			BUILD_EXTERNAL=true
		;;
	esac
done
rm -rf ${BUILD_DIR}  #  get_source_flag_for_cmsbuild.sh boostraps without using --repository to correct repo,
                     #  so wrong repository is used during boostrap which foreces to rebuild everything
CMSDIST_ONLY=true
if [ ! -z ${CMSSW_ORG} ] ; then
  CMSDIST_ONLY=false
fi
if ${BUILD_EXTERNAL} ; then
    echo_section "Building, testing and commenting status to github"
    # add special flags for pkgtools/cmsbuild if version is high enough
    if [ ${PKG_TOOL_VERSION} -ge 32 ] ; then
      REF_REPO="--reference "$(readlink /cvmfs/cms-ib.cern.ch/$(echo $CMS_WEEKLY_REPO | sed 's|^cms.||'))
      SOURCE_FLAG=$(cat ${WORKSPACE}/get_source_flag_result.txt )
    fi

    for PR in ${PULL_REQUESTS}; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        COMMIT=$(${CMS_BOT_DIR}/process-pull-request -c -r ${PR_NAME_AND_REPO} ${PR_NR})
        echo ${COMMIT} | sed 's|.* ||' > "$(get_path_to_pr_metadata ${PR})/COMMIT"
        # Notify github that the script will start testing now
        $CMS_BOT_DIR/report-pull-request-results TESTS_RUNNING --repo ${PR_NAME_AND_REPO} --pr ${PR_NR} -c ${COMMIT} \
            --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
    done

    # Not all packages are build with debug flag. If the current IB should be build with debug flag, we need to do some 'magic'
    # otherwise everything will be rebuild.
    if [ $( echo $CONFIG_LINE | grep ";ENABLE_DEBUG=" | wc -l) -eq 0 ] ; then
      DEBUG_SUBPACKS=$(grep '^ *DEBUG_SUBPACKS=' $CMS_BOT_DIR/build-cmssw-ib-with-patch | sed 's|.*DEBUG_SUBPACKS="||;s|".*$||')
      pushd ${WORKSPACE}/cmsdist
        perl -p -i -e 's/^[\s]*%define[\s]+subpackageDebug[\s]+./#subpackage debug disabled/' $DEBUG_SUBPACKS
      popd
    fi

    # Build the whole cmssw-tool-conf toolchain
    COMPILATION_CMD="pkgtools/cmsBuild --builders 3 -i $WORKSPACE/$BUILD_DIR $REF_REPO --repository $CMS_WEEKLY_REPO \
        $SOURCE_FLAG --arch $ARCHITECTURE -j $(${COMMON}/get_cpu_number.sh) build cms-common cms-git-tools cmssw-tool-conf"
    echo $COMPILATION_CMD > ${WORKSPACE}/cmsswtoolconf.log  # log the command to be run
    # run the command and both log it to file and display it
    (eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
    echo_section 'END OF BUILD LOG'

    RESULTS_FILE=$WORKSPACE/testsResults.txt
    touch $RESULTS_FILE

    TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
    GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

    echo 'CMSSWTOOLCONF_LOGS;OK,External Build Logs,See Log,..' >> $RESULTS_FILE
    if [ "X$TEST_ERRORS" != X ] || [ "X$GENERAL_ERRORS" == X ]; then
      for PR in ${PULL_REQUESTS}; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        # Report github that job failed and then exit
        ${CMS_BOT_DIR}/report-pull-request-results PARSE_BUILD_FAIL --report-pr ${PR_NR} --repo ${PR_NAME_AND_REPO} \
            --pr ${PR_NR} --pr-job-id ${BUILD_NUMBER} --unit-tests-file ${WORKSPACE}/cmsswtoolconf.log ${DRY_RUN}
      done
      # TODO there is dublication in run-cmssw.sh
      # echo 'ADDITIONAL_PRS;'$ADDITIONAL_PULL_REQUESTS >> $RESULTS_FILE # TODO do not need it, Should fix template or make new one
      echo 'PULL_REQUESTS;' ${PULL_REQUESTS} >> $RESULTS_FILE
      echo 'BASE_IB;'$CMSSW_IB >> $RESULTS_FILE
      echo 'BUILD_NUMBER;'$BUILD_NUMBER >> $RESULTS_FILE
      echo 'CMSSWTOOLCONF_RESULTS;ERROR' >> $RESULTS_FILE
      # creation of results summary file, normally done in run-pr-tests, here just to let close the process
      cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
      # TODO REPOSITORY is used to link either to CMSDIST or CMSSW repository
      sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;s|@REPOSITORY@|$PUB_REPO|g" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js  # TODO with whom replace $PUB_REPO when there is no CMSSW or CMSDIST commit?
      # -- end TODO
      exit 0
    else
      echo 'CMSSWTOOLCONF_RESULTS;OK' >> $RESULTS_FILE
    fi

    # Create an appropriate CMSSW area
    source $WORKSPACE/$BUILD_DIR/cmsset_default.sh
    echo /cvmfs/cms.cern.ch > $WORKSPACE/$BUILD_DIR/etc/scramrc/links.db
    scram -a $SCRAM_ARCH project $CMSSW_IB

    # To make sure we always pick scram from local area
    rm -f $CMSSW_IB/config/scram_basedir

    echo $(scram version) > $CMSSW_IB/config/scram_version
    if [ $(grep '^V05-07-' $CMSSW_IB/config/config_tag | wc -l) -gt 0 ] ; then
      git clone git@github.com:cms-sw/cmssw-config
      pushd cmssw-config
        git checkout master
      popd
      mv $CMSSW_IB/config/SCRAM $CMSSW_IB/config/SCRAM.orig
      cp -r cmssw-config/SCRAM $CMSSW_IB/config/SCRAM
    fi
    cd $CMSSW_IB/src

    # Setup all the toolfiles previously built
    SET_ALL_TOOLS=NO
    if [ $(echo $CMSSW_IB | grep '^CMSSW_9' | wc -l) -gt 0 ] ; then SET_ALL_TOOLS=YES ; fi
    DEP_NAMES=
    CTOOLS=../config/toolbox/${ARCHITECTURE}/tools/selected
    for xml in $(ls $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/*/tools/selected/*.xml) ; do
      name=$(basename $xml)
      tool=$(echo $name | sed 's|.xml$||')
      echo "Checking tool $tool ($xml)"
      if [ ! -e $CTOOLS/$name ] ; then
        scram setup $xml
        continue
      fi
      nver=$(grep '<tool ' $xml          | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
      over=$(grep '<tool ' $CTOOLS/$name | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
      echo "Checking version in release: $over vs $nver"
      if [ "$nver" = "$over" ] ; then continue ; fi
      echo "Settings up $name: $over vs $nver"
      DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
    done
    mv ${CTOOLS} ${CTOOLS}.backup
    mv $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/*/tools/selected ${CTOOLS}
    sed -i -e 's|.*/lib/python2.7/site-packages" .*||;s|.*/lib/python3.6/site-packages" .*||' ../config/Self.xml
    scram setup
    scram setup self
    SCRAM_TOOL_HOME=$WORKSPACE/$BUILD_DIR/share/lcg/SCRAMV1/$(cat ../config/scram_version)/src ../config/SCRAM/linkexternal.pl --arch $ARCHITECTURE --all
    scram build -r
    eval $(scram runtime -sh)
    echo $PYTHONPATH | tr ':' '\n'

    # Search for CMSSW package that might depend on the compiled externals
    touch $WORKSPACE/cmsswtoolconf.log
    if [ "X${DEP_NAMES}" != "X" ] ; then
      CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
      if [ "X${CMSSW_DEP}" != "X" ] ; then
        git cms-addpkg --ssh $CMSSW_DEP 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
      fi
    fi
fi # end of build external
echo_section "end of build external"
# TODO DELETE AFTER DEVELOPMENT
if [ ! -z COPY_STATUS ] ; then
    rm -rf ${WORKSPACE}/../SNAPSHOT/1/
    mkdir -p ${WORKSPACE}/../SNAPSHOT/1/
    cp -rf ${WORKSPACE}/* ${WORKSPACE}/../SNAPSHOT/1
fi

# Launch the pr-tests to check CMSSW by passing on the global variables
# Merge into one script
# ------ TODO included run-cmssw.sh

source ${CMS_BOT_DIR}/jenkins-artifacts
voms-proxy-init -voms cms -valid 24:00 || true  # To get access to jenkins artifact machine
ls /cvmfs/cms-ib.cern.ch || true
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
if [ "X${PUB_USER}" = X ]; then PUB_USER="cms-sw" ; fi  # TODO I need it ?

### this is for triggering the comparison with the baseline
CMSDIST_ONLY=false  #
if [ "X$PULL_REQUEST" != X ]; then   # TODO PULL_reuqest should be done something with it
  PULL_REQUEST_NUMBER=$PULL_REQUEST  # TODO Used mostly to comment and for storing jenkins artifacts
  PUB_REPO="${PUB_USER}/cmssw"       # Repo to which comments will be published
else
  # If PULL_REQUEST is empty then we are only testing a CMSDIST PR, take that
  PULL_REQUEST_NUMBER=$CMSDIST_PR
  CMSDIST_ONLY=true
  PUB_REPO="${PUB_USER}/cmsdist"
fi

# PULL_REQUEST_JOB_ID=${BUILD_NUMBER}  # TODO Not use
modify_comment_all_prs # modify comments that test are being triggered by Jenkins

cd $WORKSPACE
CONFIG_MAP=$CMS_BOT_DIR/config.map
### to know at the end of the tests if everything went ok
ALL_OK=true
BUILD_OK=true
UNIT_TESTS_OK=true
RELVALS_OK=true
ADDON_OK=true
CLANG_BUILD_OK=true
RUN_TESTS=true
REAL_ARCH=-`cat /proc/cpuinfo | grep vendor_id | head -n 1 | sed "s/.*: //"`
which scram 2>/dev/null || source /cvmfs/cms.cern.ch/cmsset_default.sh

COMPARISON_REL=
case $CMSSW_IB in
  CMSSW_9_4_MAOD_X*|CMSSW_9_4_AN_X* ) COMP_QUEUE=$(echo $CMSSW_IB | sed 's|_X.*|_X|') ;;
  * ) COMP_QUEUE=$(echo $CMSSW_IB | sed 's|^\(CMSSW_[0-9]*_[0-9]*\)_.*|\1_X|') ;;
esac

IS_DEV_BRANCH=false
DEV_BRANCH=$(grep '^ *CMSSW_DEVEL_BRANCH *= *' $CMS_BOT_DIR/releases.py | sed 's| ||g;s|.*=||;s|"||g')
if [ "X$DEV_BRANCH" = "X$COMP_QUEUE" ] ; then IS_DEV_BRANCH=true ; fi

#If a CMSSW area already exists use it as it has been prepared by the CMSDIST test script
if [ ! -d CMSSW_* ]; then
  if [[ $CMSSW_IB != *-* ]]; then
    RELEASE_QUEUE=$CMSSW_IB
    COMP_ARCH=$COMPARISON_ARCH
    if [ "X$COMP_ARCH" = "X" ] ; then
      COMP_ARCH=$(cat $CONFIG_MAP | grep $COMP_QUEUE | grep -v "DISABLED=1" | grep "PROD_ARCH=1" | cut -d ";" -f 1 | cut -d "=" -f 2)
      if [ "X$COMP_ARCH" = "X" ] ; then COMP_ARCH=$ARCHITECTURE ; fi
    fi
    for SCRAM_REL in $(scram -a $SCRAM_ARCH l -c $CMSSW_IB | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | sort -r) ;  do
      if [ "$(echo $SCRAM_REL | sed 's|_X_.*|_X|')" = "$COMP_QUEUE" ] ; then
        COMP_REL=$SCRAM_REL
      else
        COMP_REL=$(echo $SCRAM_REL | sed 's|_[A-Z][A-Z0-9]*_X_|_X_|')
      fi
      has_jenkins_artifacts ib-baseline-tests/$COMP_REL/$COMP_ARCH/$REAL_ARCH/matrix-results/wf_errors.txt || continue
      CMSSW_IB=$SCRAM_REL
      COMPARISON_ARCH=$COMP_ARCH
      COMPARISON_REL=$COMP_REL
      break
    done
    if [ "$CMSSW_IB" = "$RELEASE_QUEUE" ] ; then
      CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $RELEASE_QUEUE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | sort -r | head -1)
      if [ "X$CMSSW_IB" = "X" ] ; then
        report-pull-request-results_all_prs "RELEASE_NOT_FOUND" --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
        exit 0
      fi
    fi
  else
    RELEASE_QUEUE=`$CMS_BOT_DIR/get-pr-branch $PULL_REQUEST ${PUB_USER}/cmssw` # TODO What i am doing here with cms_pull request
  fi
else
  CMSSW_IB=$( find $WORKSPACE -maxdepth 1 -name "CMSSW_*" -printf '%f\n' )
  RELEASE_QUEUE=$( echo $CMSSW_IB | sed 's|_X.*|_X|' )
fi
[ "X$COMP_QUEUE" = "X" ] && COMP_QUEUE=$(echo $RELEASE_QUEUE | sed 's|^\(CMSSW_[0-9]*_[0-9]*\)_.*|\1_X|')

if [ "X$COMPARISON_REL" = "X" ] ; then
  case $CMSSW_IB in
    CMSSW_9_4_MAOD_X*|CMSSW_9_4_AN_X* ) COMPARISON_REL=$CMSSW_IB ;;
    * ) COMPARISON_REL=$(echo $CMSSW_IB | sed 's|_[A-Z][A-Z0-9]*_X_|_X_|')
  esac
fi

if [ "X$COMPARISON_ARCH" = "X" ] ; then
  COMPARISON_ARCH=$(cat $CONFIG_MAP | grep $COMP_QUEUE | grep -v "DISABLED=1" | grep "PROD_ARCH=1" | cut -d ";" -f 1 | cut -d "=" -f 2) #Always take the prod architecture for comparison tests.
  if [ "X$COMPARISON_ARCH" = "X" ] ; then COMPARISON_ARCH=$ARCHITECTURE ; fi
fi

USE_DAS_SORT=YES
has_jenkins_artifacts ib-baseline-tests/$COMPARISON_REL/$COMPARISON_ARCH/$REAL_ARCH/matrix-results/used-ibeos-sort || USE_DAS_SORT=NO

# TODO standardise
# creation of results summary file
# TODO for each PR's, point to repo
# TODO templates/js/renderPRTests.js - rewrite, thing how to do better ( $RESULTS_FILE )
cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;s|@REPOSITORY@|$PUB_REPO|g" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js  # TODO where to publish
RESULTS_FILE=$WORKSPACE/testsResults.txt
touch $RESULTS_FILE
echo 'PR_NUMBER;'$PULL_REQUEST_NUMBER >> $RESULTS_FILE
echo 'ADDITIONAL_PRS;'$ADDITIONAL_PULL_REQUESTS >> $RESULTS_FILE
echo 'BASE_IB;'$CMSSW_IB >> $RESULTS_FILE
echo 'BUILD_NUMBER;'$BUILD_NUMBER >> $RESULTS_FILE
# TODO --- finish
# TODO use config.map to select what test to use

if [ ! -d CMSSW_* ]; then  # if no directory that starts with "CMSSW_" exist, then bootstrap with SCRAM
  scram -a $SCRAM_ARCH  project $CMSSW_IB
  cd $CMSSW_IB
else  # else use already created one
  cd $WORKSPACE/$CMSSW_IB
fi

sed -i -e 's|^define  *processTmpMMDData.*|processTmpMMDData=true\ndefine processTmpMMDDataXX|;s|^define  *processMMDData.*|processMMDData=true\ndefine processMMDDataXX|' config/SCRAM/GMake/Makefile.rules
set +x
eval $(scram run -sh)
set -x
BUILD_LOG_DIR="${CMSSW_BASE}/tmp/${SCRAM_ARCH}/cache/log"
ANALOG_CMD="scram build outputlog && ($CMS_BOT_DIR/buildLogAnalyzer.py --logDir ${BUILD_LOG_DIR}/src || true)"
report-pull-request-results_all_prs "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Test started: $CMSSW_IB for $SCRAM_ARCH" ${DRY_RUN}

cd $WORKSPACE/$CMSSW_IB/src
git config --global --replace-all merge.renamelimit 2500

GIT_MERGE_RESULT_FILE=$WORKSPACE/git-merge-result
RECENT_COMMITS_FILE=$WORKSPACE/git-recent-commits
MB_COMPARISON=NO
touch $RECENT_COMMITS_FILE
# use the branch name if necesary
if [ "X$CMSDIST_ONLY" = Xfalse ]; then # If a CMSSW specific PR was specified #

  # this is to test several pull requests at the same time
  for PR in $( echo ${PULL_REQUESTS} | tr ' ' '\n' | grep "/cmssw#"); do
    echo 'I will add the following pull request to the test'
    PR_NR=$(echo ${PR} | sed 's/.*#//' )
    (git cms-merge-topic -u ${CMSSW_ORG}:${PR_NR} && echo 'ALL_OK') 2>&1 | tee -a $GIT_MERGE_RESULT_FILE
  done

  if grep 'Automatic merge failed' $GIT_MERGE_RESULT_FILE; then
      report-pull-request-results_all_prs "NOT_MERGEABLE" --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
    exit 0
  fi

  if grep "Couldn't find remote ref" $GIT_MERGE_RESULT_FILE; then
    echo "Please add the branch name to the parameters"
      report-pull-request-results_all_prs "REMOTE_REF_ISSUE" --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
    exit 1
  fi

  git diff --name-only $CMSSW_VERSION > $WORKSPACE/changed-files

  # look for any other error in general
  if ! grep "ALL_OK" $GIT_MERGE_RESULT_FILE; then
    echo "There was an error while running git cms-merge-topic"
      report-pull-request-results_all_prs GIT_CMS_MERGE_TOPIC_ISSUE --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
    exit 0
  fi

  #############################################
  # Check if there are unwanted commits that came with the merge.
  ############################################
  RECENT_COMMITS_LOG_FILE=$WORKSPACE/git-log-recent-commits

  #IB_DATE=$(git show ${CMSSW_IB} --pretty='format:%ai')
  git rev-list ${CMSSW_IB}..HEAD --merges 2>&1 | tee -a $RECENT_COMMITS_FILE
  git log ${CMSSW_IB}..HEAD --merges 2>&1      | tee -a $RECENT_COMMITS_LOG_FILE
  if [ $(grep 'Geometry' $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
    has_jenkins_artifacts material-budget/$CMSSW_IB/$SCRAM_ARCH/Images && MB_COMPARISON=YES
  fi
fi

#If Fireworks is the only package involved I only compile and run unit tests
ONLY_FIREWORKS=false
if [ "X$APPLY_FIREWORKS_RULE" = Xtrue ]; then
  ls $WORKSPACE/$CMSSW_IB/src
  NUM_DIRS=$(find $WORKSPACE/$CMSSW_IB/src -mindepth 1 -maxdepth 1 -type d -print | grep -v '.git' | wc -l)
  if [ "$NUM_DIRS" == 1 ]; then
    if [ -d "$WORKSPACE/$CMSSW_IB/src/Fireworks" ] ; then
      ONLY_FIREWORKS=true
      echo 'This pr only involves Fireworks!'
      echo 'Only compiling and running unit tests'
    fi
  fi
fi

# Don't do the following if we are only testing CMSDIST PR
if [ "X$CMSDIST_ONLY" == Xfalse ]; then
  # report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} ${DRY_RUN}
  git log --oneline --merges ${CMSSW_VERSION}..
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Compiling" ${DRY_RUN}
fi

# #############################################
# test compilation with Clang
# ############################################
echo 'test clang compilation'

NEED_CLANG_TEST=false
if cat $CONFIG_MAP | grep $RELEASE_QUEUE | grep PRS_TEST_CLANG= | grep SCRAM_ARCH=$ARCHITECTURE; then
  NEED_CLANG_TEST=true
fi

if [ "X$TEST_CLANG_COMPILATION" = Xtrue -a $NEED_CLANG_TEST = true -a "X$CMSDIST_PR" = X ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Testing Clang compilation" ${DRY_RUN}

  #first, add the command to the log
  CLANG_USER_CMD="USER_CUDA_FLAGS='--expt-relaxed-constexpr' USER_CXXFLAGS='-Wno-register -fsyntax-only' scram build -k -j $(${COMMON}/get_cpu_number.sh *2) COMPILER='llvm compile'"
  CLANG_CMD="scram b vclean && ${CLANG_USER_CMD} BUILD_LOG=yes && ${ANALOG_CMD}"
  echo $CLANG_USER_CMD > $WORKSPACE/buildClang.log

  (eval $CLANG_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/buildClang.log

  TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/buildClang.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/buildClang.log` || true
  for i in $(grep ": warning: " $WORKSPACE/buildClang.log | grep "/$CMSSW_IB/" | sed "s|.*/$CMSSW_IB/src/||;s|:.*||" | sort -u) ; do
    if [ $(grep "$i" $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
      echo $i >> $WORKSPACE/clang-new-warnings.log
      grep ": warning: " $WORKSPACE/buildClang.log | grep "/$i" >> $WORKSPACE/clang-new-warnings.log
    fi
  done
  if [ -e $WORKSPACE/clang-new-warnings.log ]  ; then
    echo 'CLANG_NEW_WARNINGS;ERROR,Clang Warnings to fix,See Log,clang-new-warnings.log' >> $RESULTS_FILE
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^CLANG-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      CLANG_BUILD_OK=false
    fi
  fi

  if [ -d ${BUILD_LOG_DIR}/html ] ; then
    mv ${BUILD_LOG_DIR}/html $WORKSPACE/clang-logs
    echo 'CLANG_LOG;OK,Clang warnings summary,See Log,clang-logs' >> $RESULTS_FILE
  fi
  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when testing compilation with clang"
    echo 'CLANG_COMPILATION_RESULTS;ERROR' >> $RESULTS_FILE
    RUN_TESTS=false
    ALL_OK=false
    CLANG_BUILD_OK=false
  else
    echo "the clang compilation had no errors/warnings!!"
    echo 'CLANG_COMPILATION_RESULTS;OK' >> $RESULTS_FILE
  fi
else
  echo 'CLANG_COMPILATION_RESULTS;NOTRUN' >> $RESULTS_FILE
fi

#Do QA checks
#Code Rules
QA_RES="NOTRUN"
if [ "X$CMSDIST_ONLY" == "Xfalse" ]; then # If a CMSSW specific PR was specified
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Code Rules Checks" ${DRY_RUN}
  mkdir $WORKSPACE/codeRules
  cmsCodeRulesChecker.py -s $WORKSPACE/codeRules -r 1,3 || true
  QA_RES="OK"
  for r in $(find $WORKSPACE/codeRules -name 'cmsCodeRule*.txt' -type f) ; do
    QA_COUNT=$(grep '^/' $r | sed 's|^/||' | sort | uniq | xargs -i grep '{}' $WORKSPACE/changed-files  | wc -l)
    if [ "X$QA_COUNT" = "X0" ] ; then
      rm -f $r
    else
      CRULE=$(echo $r | sed 's|.*/cmsCodeRule||;s|.txt$||')
      echo "Rule$CRULE $description: https://raw.githubusercontent.com/${PUB_USER}/cmssw/master/Utilities/ReleaseScripts/python/cmsCodeRules/config.py" > $r.new
      python -c "from Utilities.ReleaseScripts.cmsCodeRules.config import Configuration as x;print x['$CRULE']['description']" >> $r.new
      echo "" >> $r.new
      cat $r >> $r.new
      mv $r.new $r
      QA_RES="ERROR"
    fi
  done
fi
echo "CODE_RULES;${QA_RES}" >> $RESULTS_FILE

#
# Static checks
#
if [ "X$DO_STATIC_CHECKS" = "Xtrue" -a "$ONLY_FIREWORKS" = false -a "X$CMSDIST_PR" = X -a "$RUN_TESTS" = "true" ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Static Checks" ${DRY_RUN}
  echo 'STATIC_CHECKS;OK' >> $RESULTS_FILE
  echo '--------------------------------------'
  pushd $WORKSPACE/$CMSSW_IB
  git cms-addpkg --ssh Utilities/StaticAnalyzers
  mkdir $WORKSPACE/llvm-analysis
  USER_CXXFLAGS='-Wno-register' SCRAM_IGNORE_PACKAGES="Fireworks/% Utilities/StaticAnalyzers" USER_LLVM_CHECKERS="-enable-checker threadsafety -enable-checker cms -disable-checker cms.FunctionDumper" \
    scram b -k -j $(${COMMON}/get_cpu_number.sh *2) checker SCRAM_IGNORE_SUBDIRS=test 2>&1 | tee -a $WORKSPACE/llvm-analysis/runStaticChecks.log
  cp -R $WORKSPACE/$CMSSW_IB/llvm-analysis/*/* $WORKSPACE/llvm-analysis || true
  echo 'END OF STATIC CHECKS'
  echo '--------------------------------------'
  popd
else
  echo 'STATIC_CHECKS;NOTRUN' >> $RESULTS_FILE
fi

scram build clean
git cms-checkdeps -A -a
CMSSW_PKG_COUNT=$(ls -d $LOCALRT/src/*/* | wc -l)
############################################
# Force the run of DQM tests if necessary
############################################
if ls $WORKSPACE/$CMSSW_IB/src/| grep -i -E "dqm.*|HLTriggerOffline|Validation"; then
  echo "I will make sure that DQM tests will be run"
  if ls $WORKSPACE/$CMSSW_IB/src/| grep "DQMServices"; then
    echo DQMServices is already there
      if ls $WORKSPACE/$CMSSW_IB/src/DQMServices/| grep "Components"; then
        echo "and DQMServices/Components is there"
      else
        git cms-addpkg --ssh DQMServices/Components
      fi
  else
    echo "checking out DQMServices"
    git cms-addpkg --ssh DQMServices
  fi
fi
#############################################
# Remove poison if asked to do so
#############################################
if [ "X$DISABLE_POISON" = Xtrue ]; then
  if [ -d $WORKSPACE/CMSSW_*/poison ]; then
    rm -rf $WORKSPACE/CMSSW_*/poison
  fi
fi
# #############################################
# test header checks tests
# ############################################
CHK_HEADER_LOG_RES="NOTRUN"
CHK_HEADER_OK=true
if [ -f $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.chk_headers ] ; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running HeaderChecks" ${DRY_RUN}
  COMPILATION_CMD="scram b vclean && USER_CHECK_HEADERS_IGNORE='TrackingTools/GsfTools/interface/MultiGaussianStateCombiner.h %.i' scram build -k -j $(${COMMON}/get_cpu_number.sh) check-headers"
  echo $COMPILATION_CMD > $WORKSPACE/headers_chks.log
  (eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/headers_chks.log
  echo 'END OF HEADER CHEKS LOG'
  TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/headers_chks.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/headers_chks.log` || true
  CHK_HEADER_LOG_RES="OK"
  CHK_HEADER_OK=true
  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    CHK_HEADER_LOG_RES="ERROR"
    CHK_HEADER_OK=false
  fi
fi
echo "HEADER_CHECKS;${CHK_HEADER_LOG_RES},Header Consistency,See Log,headers_chks.log" >> $RESULTS_FILE
# #############################################
# test compilation with GCC
# ############################################
report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Compilation" ${DRY_RUN}
COMPILATION_CMD="scram b vclean && BUILD_LOG=yes scram b -k -j $(${COMMON}/get_cpu_number.sh) && ${ANALOG_CMD}"
if [ "X$CMSDIST_PR" != X -a $(grep '^edm_checks:' $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.rules | wc -l) -gt 0 ] ; then
  COMPILATION_CMD="scram b vclean && BUILD_LOG=yes SCRAM_NOEDM_CHECKS=yes scram b -k -j $(${COMMON}/get_cpu_number.sh) && ${ANALOG_CMD} && scram b -k -j $(${COMMON}/get_cpu_number.sh) edm_checks"
fi
echo $COMPILATION_CMD > $WORKSPACE/build.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/build.log
if [ -d ${BUILD_LOG_DIR}/html ] ; then mv ${BUILD_LOG_DIR}/html ${WORKSPACE}/build-logs ; fi
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/build.log` || true
GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/build.log` || true

for i in $(grep ": warning: " $WORKSPACE/build.log | grep "/$CMSSW_IB/" | sed "s|.*/$CMSSW_IB/src/||;s|:.*||" | sort -u) ; do
  if [ $(grep "$i" $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
    echo $i >> $WORKSPACE/new-build-warnings.log
    grep ": warning: " $WORKSPACE/build.log | grep "/$i" >> $WORKSPACE/new-build-warnings.log
  fi
done
if [ -e $WORKSPACE/new-build-warnings.log ]  ; then
    echo 'BUILD_NEW_WARNINGS;ERROR,Compilation Warnings to fix,See Log,new-build-warnings.log' >> $RESULTS_FILE
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^BUILD-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      BUILD_OK=false
    fi
fi
BUILD_LOG_RES="ERROR"
if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when building"
    echo 'COMPILATION_RESULTS;ERROR' >> $RESULTS_FILE
    RUN_TESTS=false
    ALL_OK=false
    BUILD_OK=false
else
    echo "the build had no errors!!"
    echo 'COMPILATION_RESULTS;OK' >> $RESULTS_FILE
    if [ -e ${WORKSPACE}/build-logs/index.html ] ; then
      if [ $(grep '<td> *[1-9][0-9]* *</td>' ${WORKSPACE}/build-logs/index.html  | grep -iv ' href' | grep -v 'ignoreWarning' | wc -l) -eq 0 ] ; then
        BUILD_LOG_RES="OK"
      fi
    elif [ ! -d ${BUILD_LOG_DIR}/src ] ; then
      BUILD_LOG_RES="OK"
    fi
fi
echo "BUILD_LOG;${BUILD_LOG_RES}" >> $RESULTS_FILE

#Copy the cmssw ib das_client wrapper in PATH
cp -f $CMS_BOT_DIR/das-utils/das_client $CMS_BOT_DIR/das-utils/das_client.py
##FIXME: Remove the following das_client.py link once all IBs use das_client wrapper
set +x ; eval $(scram run -sh) ;set -x
#Drop RELEASE_TOP/external/SCRAM_ARCH/data if LOCALTOP/external/SCRAM_ARCH/data exists
#to make sure external packages removed files are not picked up from release directory
if [ "X$CMSDIST_PR" != "X" ] ; then
  export CMSSW_SEARCH_PATH=$(echo $CMSSW_SEARCH_PATH | tr ':' '\n'  | grep -v "$CMSSW_RELEASE_BASE/external/" | tr '\n' ':')
fi
export PATH=$CMS_BOT_DIR/das-utils:$PATH
which das_client

[ "X$USE_DAS_SORT" = "XYES" ] && $CMS_BOT_DIR/das-utils/use-ibeos-sort

#Duplicate dict
QA_RES="NOTRUN"
if [ "X$DO_DUPLICATE_CHECKS" = Xtrue -a "$ONLY_FIREWORKS" = false -a "X$CMSDIST_ONLY" == "Xfalse" -a "$RUN_TESTS" = "true" ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Duplicate Dict Checks" ${DRY_RUN}
  mkdir $WORKSPACE/dupDict
  QA_RES="OK"
  for type in dup lostDefs edmPD ; do
    duplicateReflexLibrarySearch.py --${type} 2>&1 | grep -v ' SKIPPING ' > $WORKSPACE/dupDict/${type}.txt || true
  done
  QA_COUNT=$(cat $WORKSPACE/dupDict/dup.txt | grep '^  *[.]/[A-Z]' | sed 's|^  *./||' | sort | uniq | xargs -i grep '{}' $WORKSPACE/changed-files  | wc -l)
  if [ "X$QA_COUNT" != "X0" ] ; then QA_RES="ERROR" ; fi
  QA_COUNT=$(cat $WORKSPACE/dupDict/lostDefs.txt | grep '^[.]/[A-Z]' | sed 's|^./||' | sort | uniq | xargs -i grep '{}' $WORKSPACE/changed-files  | wc -l)
  if [ "X$QA_COUNT" != "X0" ] ; then QA_RES="ERROR" ; fi
  if [ -s $WORKSPACE/dupDict/edmPD ] ; then QA_RES="ERROR" ; fi
fi
echo "DUPLICATE_DICT_RULES;${QA_RES}" >> $RESULTS_FILE

#
# Unit tests
#
if [ "X$DO_TESTS" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$RUN_TESTS" = "true" ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Unit Tests" ${DRY_RUN}
  echo '--------------------------------------'
  UT_TIMEOUT=$(echo 7200+${CMSSW_PKG_COUNT}*20 | bc)
  UTESTS_CMD="CMS_PATH=/cvmfs/cms-ib.cern.ch/week0 timeout ${UT_TIMEOUT} scram b -k -j $(${COMMON}/get_cpu_number.sh)  runtests "
  echo $UTESTS_CMD > $WORKSPACE/unitTests.log
  (eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/unitTests.log 2>&1
  echo 'END OF UNIT TESTS'
  echo '--------------------------------------'
  #######################################
  # check if DQM Tests where run
  #######################################
  if ls $WORKSPACE/$CMSSW_IB/src/DQMServices/Components/test/ | grep -v -E "[a-z]+"; then
    echo "DQM Tests were run!"
    pushd $WORKSPACE/$CMSSW_IB/src/DQMServices/Components/test/
    ls | grep -v -E "[a-z]+" | xargs -I ARG mv ARG DQMTestsResults
    mkdir $WORKSPACE/DQMTestsResults
    cp -r DQMTestsResults $WORKSPACE/DQMTestsResults
    ls $WORKSPACE
    popd

    echo 'DQM_TESTS;OK' >> $RESULTS_FILE
  else
    echo 'DQM_TESTS;NOTRUN' >> $RESULTS_FILE
  fi

  TEST_ERRORS=$(grep -i 'had errors\|recipe for target' $WORKSPACE/unitTests.log | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
  TEST_ERRORS=`grep -i "had errors" $WORKSPACE/unitTests.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/unitTests.log` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the unit tests"
    echo 'UNIT_TEST_RESULTS;ERROR' >> $RESULTS_FILE
    ALL_OK=false
    UNIT_TESTS_OK=false
  else
    echo 'UNIT_TEST_RESULTS;OK' >> $RESULTS_FILE
  fi

else
  echo 'UNIT_TEST_RESULTS;NOTRUN' >> $RESULTS_FILE
  echo 'DQM_TESTS;NOTRUN' >> $RESULTS_FILE

fi

#
# Matrix tests
#

MATRIX_EXTRAS=$(echo $(grep 'PR_TEST_MATRIX_EXTRAS=' $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||'),${MATRIX_EXTRAS} | tr ' ' ','| tr ',' '\n' | grep '^[0-9]' | sort | uniq | tr '\n' ',' | sed 's|,*$||')
if [ ! "X$MATRIX_EXTRAS" = X ]; then
  MATRIX_EXTRAS="-l $MATRIX_EXTRAS"
fi

if [ "X$DO_SHORT_MATRIX" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$ONLY_FIREWORKS" = false -a "$RUN_TESTS" = "true" ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running RelVals" ${DRY_RUN}
  echo '--------------------------------------'
  mkdir "$WORKSPACE/runTheMatrix-results"
  pushd "$WORKSPACE/runTheMatrix-results"
    case $CMSSW_IB in
      *SLHCDEV*)
        SLHC_PARAM='-w upgrade'
        WF_LIST="-l 10000,10061,10200,10261,10800,10861,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
        ;;
      *SLHC*)
        SLHC_PARAM='-w upgrade'
        WF_LIST="-l 10000,10061,10200,10261,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
        ;;
      *)
        WF_LIST="-s $MATRIX_EXTRAS"
        ;;
    esac

    # MATRIX_TIMEOUT is set by jenkins
    dateBefore=$(date +"%s")
    [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && EXTRA_MATRIX_ARGS="--job-reports $EXTRA_MATRIX_ARGS"
    RELVALS_CMD="CMS_PATH=/cvmfs/cms-ib.cern.ch/week0 timeout $MATRIX_TIMEOUT runTheMatrix.py $EXTRA_MATRIX_ARGS $SLHC_PARAM -j $(${COMMON}/get_cpu_number.sh -2) $WF_LIST"
    echo $RELVALS_CMD > $WORKSPACE/matrixTests.log
    (eval $RELVALS_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/matrixTests.log
    WORKFLOW_TO_COMPARE=$(grep '^[1-9][0-9]*' $WORKSPACE/matrixTests.log | grep ' Step[0-9]' | sed 's|_.*||' | tr '\n' ',' | sed 's|,$||')

    dateAfter=$(date +"%s")
    diff=$(($dateAfter-$dateBefore))

    if [ "$diff" -ge $MATRIX_TIMEOUT ]; then
      echo "------------"  >> $WORKSPACE/matrixTests.log
      echo 'ERROR TIMEOUT' >> $WORKSPACE/matrixTests.log
    fi
  popd

  TEST_ERRORS=`grep -i -E "ERROR .*" $WORKSPACE/matrixTests.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/matrixTests.log` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the RelVals"
    echo 'MATRIX_TESTS;ERROR' >> $RESULTS_FILE
    echo 'COMPARISON;NOTRUN' >> $RESULTS_FILE
    ALL_OK=false
    RELVALS_OK=false
  else
    echo "no errors in the RelVals!!"
    echo 'MATRIX_TESTS;OK' >> $RESULTS_FILE
    echo 'COMPARISON;QUEUED' >> $RESULTS_FILE

    TRIGGER_COMPARISON_FILE=$WORKSPACE/'comparison.properties'
    echo "Creating properties file $TRIGGER_COMPARISON_FILE"
    echo "CMSSW_IB=$COMPARISON_REL" > $TRIGGER_COMPARISON_FILE
    echo "ARCHITECTURE=${ARCHITECTURE}" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUEST_NUMBER=$PULL_REQUEST_NUMBER" >> $TRIGGER_COMPARISON_FILE  # TODO how to substitute
    echo "PULL_REQUEST_JOB_ID=${BUILD_NUMBER}" >> $TRIGGER_COMPARISON_FILE
    echo "REAL_ARCH=$REAL_ARCH" >> $TRIGGER_COMPARISON_FILE
    echo "WORKFLOWS_LIST=${WORKFLOW_TO_COMPARE}" >> $TRIGGER_COMPARISON_FILE
    echo "COMPARISON_ARCH=$COMPARISON_ARCH" >> $TRIGGER_COMPARISON_FILE
    echo "CMSDIST_ONLY=$CMSDIST_ONLY" >> $TRIGGER_COMPARISON_FILE
    echo "PUB_REPO=$PUB_REPO" >> $TRIGGER_COMPARISON_FILE

    #####################################################################
    #### Run igprof
    #####################################################################
    # for now this is only run for 25202

    if [ "X$RUN_IGPROF" = Xtrue ]; then
      echo 'IGPROF;QUEQUED' >> $RESULTS_FILE

      TRIGGER_IGPROF_FILE=$WORKSPACE/'igprof.properties'
      echo "Creating properties file $TRIGGER_IGPROF_FILE"
      echo "CMSSW_IB=$CMSSW_IB" > $TRIGGER_IGPROF_FILE
      echo "ARCHITECTURE=${ARCHITECTURE}" >> $TRIGGER_IGPROF_FILE
      echo "PULL_REQUEST_NUMBER=$PULL_REQUEST_NUMBER" >> $TRIGGER_IGPROF_FILE
      echo "PULL_REQUEST_JOB_ID=${BUILD_NUMBER}" >> $TRIGGER_IGPROF_FILE
      echo "LAST_COMMIT=${LAST_COMMIT}" >> $TRIGGER_IGPROF_FILE
      echo "AUTO_POST_MESSAGE=${AUTO_POST_MESSAGE}" >> $TRIGGER_IGPROF_FILE
    else
      echo 'IGPROF;NOTRUN' >> $RESULTS_FILE
    fi

    #####################################################################
    #### Run cfg-viewer
    #####################################################################

    if [ "X$RUN_CONFIG_VIEWER" = Xtrue ]; then
      mkdir -p "$WORKSPACE/cfg-viewerResults"
      pushd "$WORKSPACE/cfg-viewerResults"
        cfg-viewer.py -r -s "$WORKSPACE/runTheMatrix-results"
      popd
      sed -i "s/<!--CONFIG_FILES_BROWSER//g" $WORKSPACE/summary.html
      sed -i "s/CONFIG_FILES_BROWSER-->//g" $WORKSPACE/summary.html
      sed -i "s/PARAM_CONFIG_BROWSER/https:\/\/cmssdt.cern.ch\/SDT\/${JENKINS_PREFIX}-artifacts\/${JOB_NAME}\/PR-${PULL_REQUEST}\/${BUILD_NUMBER}\/cfg-viewerResults\//g" $WORKSPACE/summary.html
    fi
  fi
else
  echo 'MATRIX_TESTS;NOTRUN' >> $RESULTS_FILE
  echo 'COMPARISON;NOTRUN' >> $RESULTS_FILE
  echo 'IGPROF;NOTRUN' >> $RESULTS_FILE
fi

#
# AddOn Tetss
#
if [ "X$DO_ADDON_TESTS" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$RUN_TESTS" = "true" ]; then
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running AddOn Tests" ${DRY_RUN}
  #Some data files in cmssw_7_1/src directory are newer then cmsswdata. We make sure that we pick up these files from src instead of data.
  #Without this hack, pat1 addOnTest fails.
  EX_DATA_SEARCH="$CMSSW_SEARCH_PATH"
  case $CMSSW_IB in
    CMSSW_7_1_* )
      for xdata_pkg in Geometry/CMSCommonData Geometry/ForwardCommonData Geometry/HcalCommonData Geometry/MuonCommonData Geometry/TrackerCommonData ; do
        if [ -e ${CMSSW_BASE}/external/${SCRAM_ARCH}/data/${xdata_pkg}/data ] ; then
          if [ ! -e ${CMSSW_BASE}/src/${xdata_pkg}/data ] ; then
            mkdir -p ${CMSSW_BASE}/xdata/${xdata_pkg}
            ln -s $CMSSW_RELEASE_BASE/src/${xdata_pkg}/data ${CMSSW_BASE}/xdata/${xdata_pkg}/data
            EX_DATA_SEARCH="${CMSSW_BASE}/xdata:$CMSSW_SEARCH_PATH"
          fi
        fi
      done
    ;;
  esac
  #End of 71x data hack
  echo '--------------------------------------'
  date
  ADDON_CMD="CMSSW_SEARCH_PATH=$EX_DATA_SEARCH CMS_PATH=/cvmfs/cms-ib.cern.ch/week0 timeout 7200 addOnTests.py -j $(${COMMON}/get_cpu_number.sh)"
  echo $ADDON_CMD > $WORKSPACE/addOnTests.log
  (eval $ADDON_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/addOnTests.log
  date
  echo 'END OF ADDON TESTS'
  echo '--------------------------------------'
  if [ -d addOnTests ] ; then
    mv addOnTests $WORKSPACE/addOnTests
  fi
  TEST_ERRORS=`grep -i -E ": FAILED .*" $WORKSPACE/addOnTests.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/addOnTests.log` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the addOnTests"
    echo 'ADDON_TESTS;ERROR' >> $RESULTS_FILE
    ALL_OK=false
    ADDON_OK=false
  else
    echo "no errors in the addOnTests!!"
    echo 'ADDON_TESTS;OK' >> $RESULTS_FILE
  fi
else
  echo 'ADDON_TESTS_RESULTS;NOTRUN' >> $RESULTS_FILE
fi

MB_TESTS_OK=NOTRUN
if [ "$MB_COMPARISON" = "YES" -a "X$BUILD_OK" = "Xtrue" -a "$RUN_TESTS" = "true" ] ; then
  if has_jenkins_artifacts material-budget/${CMSSW_VERSION}/${SCRAM_ARCH}/Images ; then
    mkdir $LOCALRT/material-budget
    MB_TESTS_OK=OK
    pushd $LOCALRT/material-budget
      $CMS_BOT_DIR/run-material-budget > $WORKSPACE/material-budget.log 2>&1 || MB_TESTS_OK=ERROR
      if [ "$MB_TESTS_OK" = "OK" ] ; then
        $CMS_BOT_DIR/compare-material-budget $LOCALRT/material-budget || MB_TESTS_OK=ERROR
      fi
    popd
    mv $LOCALRT/material-budget $WORKSPACE/material-budget
  fi
fi
echo "MATERIAL_BUDGET;${MB_TESTS_OK}" >> $RESULTS_FILE
if [ "$MB_TESTS_OK" = "ERROR" ] ; then
  MB_TESTS_OK=false
else
  MB_TESTS_OK=true
fi

#
# Valgrind tests
#
for WF in ${WORKFLOWS_FOR_VALGRIND_TEST//,/ }; do
  report-pull-request-results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} --add-message "Running Valgrind" ${DRY_RUN}

  echo 'I will run valgrind for the following workflow'
  echo $WF;
  mkdir -p "$WORKSPACE/valgrindResults-"$WF
  pushd "$WORKSPACE/valgrindResults-"$WF
  runTheMatrix.py --command '-n 10 --prefix "time valgrind --tool=memcheck --suppressions=$CMSSW_RELEASE_BASE/src/Utilities/ReleaseScripts/data/cms-valgrind-memcheck.supp --num-callers=20 --xml=yes --xml-file=valgrind.xml " ' -l $WF
  popd
done

# TODO DELETE AFTER DEVELOPMENT
if [ ! -z COPY_STATUS ] ; then
    rm -rf ${WORKSPACE}/../SNAPSHOT/2/
    mkdir -p ${WORKSPACE}/../SNAPSHOT/2/
    cp -rf ${WORKSPACE}/* ${WORKSPACE}/../SNAPSHOT/2/
fi
# TODO DELETE AFTER DEVELOPMENT
#evaluate results
REPORT_H_CODE=$( echo ${PULL_REQUESTS} | md5sum | sed 's| .*||' )      # Used to to create link to folder where uploaded files are.

TESTS_FAILED="Failed tests:"
if [ "X$BUILD_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  Build"
  if [ "X$CHK_HEADER_OK" = Xfalse ] ; then
    TESTS_FAILED="$TESTS_FAILED  HeaderConsistency"
  fi
fi
if [ "X$UNIT_TESTS_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  UnitTests"
fi
if [ "X$RELVALS_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  RelVals"
fi
if [ "X$ADDON_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  AddOn"
fi
if [ "X$CLANG_BUILD_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  ClangBuild"
fi

cd $WORKSPACE
mkdir -p upload
for f in build-logs clang-logs runTheMatrix-results llvm-analysis *.log *.html *.txt *.js DQMTestsResults valgrindResults-* cfg-viewerResults igprof-results-data git-merge-result git-log-recent-commits addOnTests codeRules dupDict material-budget ; do
  [ -e $f ] && mv $f upload/$f
done
[ -e upload/renderPRTests.js ] && mkdir -p upload/js && mv upload/renderPRTests.js upload/js/
[ -e upload/matrixTests.log  ] && mkdir -p upload/runTheMatrix-results && mv upload/matrixTests.log upload/runTheMatrix-results/
[ -d upload/addOnTests       ] && find upload/addOnTests -name '*.root' -type f | xargs rm -f

rm -f ${WORKSPACE}/report.txt
REPORT_OPTS="--report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --recent-merges $RECENT_COMMITS_FILE $DRY_RUN"

if ${ALL_OK} ; then  # if non of the test failed (non of them set ALL_OK to false)
    if [ "${BUILD_LOG_RES}" = "ERROR" ] ; then
        BUILD_LOG_RES=" --add-comment 'Compilation Warnings: Yes'"
    else
        BUILD_LOG_RES=""
    fi
    REPORT_OPTS="TESTS_OK_PR ${REPORT_OPTS} ${BUILD_LOG_RES}"
else
    # Doc: in case some test failed, we check each test log specifically and generate combined message
    # which is stored in $WORKSPACE/report.txt
    # $WORKSPACE/report.txt - is used to write message to unless its 'REPORT_ERRORS', then it is read from to upload comment
    REPORT_OPTS="--report-file $WORKSPACE/report.txt ${REPORT_OPTS}"
    # Doc: --repo and --pr are not used in report, but is a must for script, so I put a placeholder
    REPORT_GEN_OPTS="--repo cms-sw/cmssw --pr 1 ${REPORT_OPTS} "  #

    echo "**${TESTS_FAILED}**" >  $WORKSPACE/report.txt
    if [ "X$BUILD_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL       -f $WORKSPACE/upload/build.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$UNIT_TESTS_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PARSE_UNIT_TESTS_FAIL  -f $WORKSPACE/upload/unitTests.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$RELVALS_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PARSE_MATRIX_FAIL      -f $WORKSPACE/upload/runTheMatrix-results/matrixTests.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$ADDON_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PARSE_ADDON_FAIL       -f $WORKSPACE/upload/addOnTests.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$CLANG_BUILD_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PARSE_CLANG_BUILD_FAIL -f $WORKSPACE/upload/buildClang.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$MB_TESTS_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results MATERIAL_BUDGET        -f $WORKSPACE/upload/material-budget.log ${REPORT_GEN_OPTS}
    fi
    REPORT_OPTS="REPORT_ERRORS ${REPORT_OPTS}" # Doc:
fi

rm -f all_done  # delete file
if [ -z ${DRY_RUN} ]; then
    send_jenkins_artifacts $WORKSPACE/upload pull-request-integration/PR-${REPORT_H_CODE}/${BUILD_NUMBER} && touch all_done  # TODO aha, what to do here ?
    if [ -d $LOCALRT/das_query ] ; then
      send_jenkins_artifacts $LOCALRT/das_query das_query/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/PR || true  # TODO make a hash
    fi
fi

if [ -f all_done ] ; then
  rm -f all_done
    # Doc: report everything back unless no matter if ALL_OK was true or false.
    report-pull-request-results_all_prs_with_commit ${REPORT_OPTS}
else
  exit 1 # Doc: if upload to jenkins failed, exit with error
fi

COMP_MSG="Comparison job queued."
if [ $(grep 'COMPARISON;NOTRUN' $WORKSPACE/upload/testsResults.txt | wc -l) -gt 0 ] ; then
  ERR_MSG="Build errors/Fireworks only changes/No short matrix requested"
  if [ "X$BUILD_OK" != "Xtrue" ] ; then
    ERR_MSG="Build errors"
  elif [ "X$RELVALS_OK" != "Xtrue" ] ; then
    ERR_MSG="runTheMatrix errors"
  elif [ "X$DO_SHORT_MATRIX" != "Xtrue" ] ; then
    ERR_MSG="short runTheMatrix was not requested"
  elif [ "X$ONLY_FIREWORKS" = "Xtrue" ] ; then
    ERR_MSG="Fireworks only changes in PR"
  fi
  COMP_MSG="Comparison not run due to ${ERR_MSG} (RelVals and Igprof tests were also skipped)"
fi

# Leave final comment
for PR in ${PULL_REQUESTS} ; do
    PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
    PR_NR=$(echo ${PR} | sed 's/.*#//' )
    ${CMS_BOT_DIR}/comment-gh-pr -r ${PR_NAME_AND_REPO} -p ${PR_NR} -m "${COMP_MSG}" ${DRY_RUN} || true
done