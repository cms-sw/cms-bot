#!/bin/bash -ex
# This script will be called by Jenkins job ( TODO what job)
# and
# 1) will merge multiple PRs for multiple repos
# 2) run tests and post result on github
# ---
# Constants
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )

CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
BUILD_DIR="testBuildDir"  # Where pkgtools/cmsBuild builds software
# ---

## TODO check if the variable there

# Input variable
PULL_REQUESTS=$PULL_REQUESTS              # "cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116"
RELEASE_FORMAT=$RELEASE_FORMAT             # CMS SW TAG found in config_map.py
#PULL_REQUEST=$PULL_REQUEST
CMSDIST_PR=$CMSDIST_PR
ARCHITECTURE=$ARCHITECTURE               # architecture (ex. slc6_amd64_gcc700)
# RELEASE_FORMAT=           # RELEASE_QUEUE found in config_map.py (ex. CMSSW_10_4_ROOT6_X )
# DO_TESTS=
# DO_SHORT_MATRIX=
# DO_STATIC_CHECKS=
# DO_DUPLICATE_CHECKS=
# MATRIX_EXTRAS=
ADDITIONAL_PULL_REQUESTS=$ADDITIONAL_PULL_REQUESTS   # aditonal CMSSW PRs
# WORKFLOWS_FOR_VALGRIND_TEST=
# AUTO_POST_MESSAGE=
# RUN_CONFIG_VIEWER=
# USE_DAS_CACHE=
# BRANCH_NAME=
# APPLY_FIREWORKS_RULE=
# RUN_IGPROF=
# TEST_CLANG_COMPILATION=
# MATRIX_TIMEOUT=
# EXTRA_MATRIX_ARGS=
# DO_ADDON_TESTS=
# RUN_ON_SLAVE=
# COMPARISON_ARCH=
# DISABLE_POISON=
# FULL_TOOLCONF=
PUB_USER=$PUB_USER
DRY_RUN=$DRY_RUN

WORKSPACE=$WORKSPACE
USER=$USER
BUILD_NUMBER=$BUILD_NUMBER
JOB_NAME=$JOB_NAME


# -- Functions
function echo_section(){
    echo "---------|  $1  |----------"
}

function fail_if_empty(){
    if [ -z $(echo "$1" | tr -d ' ' ) ]; then
        >&2 echo "ERROR: empty variable. ${2}."
        exit 1
    fi
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    PR_METADATA_PATH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "$1")
    echo ${PR_METADATA_PATH}
    EXTERNAL_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
    fail_if_empty "${EXTERNAL_BRANCH}" "PR had errors - ${1}"
    echo ${EXTERNAL_BRANCH}
}

# -- MAIN --
echo_section "Variable setup"
CMSSW_CYCLE=$(echo ${RELEASE_FORMAT} | sed 's/_X.*/_X/')  # RELEASE_FORMAT - CMSSW_10_4_X_2018-11-26-2300
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | sed 's/ //g' | tr ',' ' ')
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )  # Repos without pull number
fail_if_empty "${UNIQ_REPOS}" "UNIQ_REPOS"
UNIQ_REPO_NAMES=$(echo ${UNIQ_REPOS} | tr ' ' '\n' | sed 's|.*/||' )
UNIQ_REPO_NAMES_WITH_COUNT=$(echo ${UNIQ_REPO_NAMES} | sort | uniq -c )

CMS_WEEKLY_REPO=cms.week$(echo $(tail -1 $CMS_BOT_DIR/ib-weeks | sed 's|.*-||') % 2 | bc)
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${PUB_USER}" = X ] ; then export PUB_USER="cms-sw" ; fi

export ARCHITECTURE
export SCRAM_ARCH=${ARCHITECTURE}
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
        PR_METADATA_PATH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "${CMSDIST_PR}")
        # CMSSW branch name is release cycle
        CMSSW_CYCLE=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
     elif [[ ! -z ${CMSSW_PR} && -z ${CMSSW_CYCLE} ]] ; then
        CMSSW_METADATA_PATH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "${CMSSW_PR}")
        SW_BASE_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
        CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "" "${SW_BASE_BRANCH}" "${ARCHITECTURE}")
        CMSSW_CYCLE=$(echo ${CONFIG_LINE} | sed 's/^.*RELEASE_QUEUE=//' | sed 's/;.*//' )
     fi
fi
fail_if_empty "${CMSSW_CYCLE}" "CMSSW release cycle unsent and could not be determined."

CMSSW_IB=  # We are getting CMSSW_IB, so that we wont rebuild all the software
for relpath in $(scram -a $ARCHITECTURE l -c $CMSSW_CYCLE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests"  | awk '{print $2":"$3}' | sort -r | sed 's|^.*:||') ; do
  [ -e $relpath/build-errors ] && continue
  CMSSW_IB=$(basename $relpath)
  break
done
[ "X$CMSSW_IB" = "X" ] && CMSSW_IB=$(scram -a $ARCHITECTURE l -c ${CMSSW_CYCLE} | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | tail -n 1)

if [ -z ${CONFIG_LINE} ] ; then  # Get config line
    CONFIG_LINE=$(${COMMON}/get_config_map_line.sh "${CMSSW_CYCLE}" "" "${ARCHITECTURE}" )
fi
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
        ${PR_TESTING_DIR}/git_clone_and_merge.sh "$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "${PR}")"
    done
done

# Preparations depending on from repo type
for U_REPO in ${UNIQ_REPOS}; do
    PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
    PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
    case "$PKG_NAME" in  # We do not care where the repo is kept (ex. cmssw organisation or other)
		cmssw)
            PUB_REPO=${PKG_REPO}  # PUB_REPO is used for publishing results
		;;
		cmsdist)
            if [ -z ${PUB_REPO} ] ; then PUB_REPO=${PKG_REPO} ; fi  # if PUB_REPO repo not set to cmssw, use cmsdist
		;;
		*)
			PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
			PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
			${PR_TESTING_DIR}/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$PKG_NAME" "$CMSSW_CYCLE" "$ARCHITECTURE"
		;;
	esac
done

echo_section "Building, testing and commenting status to github"
# add special flags for pkgtools/cmsbuild if version is high enough
if [ ${PKG_TOOL_VERSION} -ge 32 ] ; then
  REF_REPO="--reference "$(readlink /cvmfs/cms-ib.cern.ch/$(echo $CMS_WEEKLY_REPO | sed 's|^cms.||'))
  SOURCE_FLAG=$(cat ${WORKSPACE}/get_source_flag_result.txt )
fi
if [ -z ${DRY_RUN} ] ; then  # if NOT dry run, comment
    for PR in ${PULL_REQUESTS}; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        COMMIT=$(${CMS_BOT_DIR}/process-pull-request -c -r ${PR_NAME_AND_REPO} ${PR_NR})
        # if CMSDIST commit, export it to available in run-pr-test
        if [[ -z $( echo ${PR_NAME_AND_REPO} | sed 's|.*/||' | grep -w cmsdist ) ]] ; then
            echo "TODO"
            export CMSDIST_COMMIT=$(echo ${COMMIT} | sed 's|.* ||')  # TODO do I need CMSDIST_COMMIT in run-pr-test ?
        fi
        # Notify github that the script will start testing now
        $CMS_BOT_DIR/report-pull-request-results TESTS_RUNNING --repo ${PR_NAME_AND_REPO} --pr ${PR_NR} -c ${COMMIT} --pr-job-id ${BUILD_NUMBER}
    done
fi

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
  $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL --report-pr $CMSDIST_PR --repo ${PUB_USER}/cmsdist --pr $CMSDIST_PR -c $CMSDIST_COMMIT --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log
  if [ "X$PULL_REQUEST" != X ]; then
    $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL --report-pr $CMSDIST_PR  --repo ${PUB_USER}/cmssw --pr $PULL_REQUEST --pr-job-id ${BUILD_NUMBER} --unit-tests-file $WORKSPACE/cmsswtoolconf.log
  fi
  echo 'PR_NUMBER;'$CMSDIST_PR >> $RESULTS_FILE
  echo 'ADDITIONAL_PRS;'$ADDITIONAL_PULL_REQUESTS >> $RESULTS_FILE
  echo 'BASE_IB;'$CMSSW_IB >> $RESULTS_FILE
  echo 'BUILD_NUMBER;'$BUILD_NUMBER >> $RESULTS_FILE
  echo 'CMSSWTOOLCONF_RESULTS;ERROR' >> $RESULTS_FILE
  # creation of results summary file, normally done in run-pr-tests, here just to let close the process
  cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
  sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;s|@REPOSITORY@|$PUB_REPO|g" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js
  exit 0
else
  echo 'CMSSWTOOLCONF_RESULTS;OK' >> $RESULTS_FILE
fi

# Create an appropriate CMSSW area
source $WORKSPACE/$BUILD_DIR/cmsset_default.sh
echo /cvmfs/cms.cern.ch > $WORKSPACE/$BUILD_DIR/etc/scramrc/links.db
scram -a $SCRAM_ARCH project $CMSSW_IB

# TO make sure we always pick scram from local area
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
# Launch the standard ru-pr-tests to check CMSSW side passing on the global variables
# $CMS_BOT_DIR/run-pr-tests  # TODO - fix jenkins artifacts do nothing
