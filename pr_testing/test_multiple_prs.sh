#!/bin/bash -ex
# This script will be called by Jenkins job 'ib-run-pr-tests'
# and
# 1) will merge multiple PRs for multiple repos
# 2) run tests and post result on github
# ---
# Constants
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
source ${CMS_BOT_DIR}/cmsrep.sh

CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
BUILD_DIR="testBuildDir"  # Where pkgtools/cmsBuild builds software
RESULTS_FILE=$WORKSPACE/testsResults
CONFIG_MAP=$CMS_BOT_DIR/config.map
rm -rf ${RESULTS_FILE} ${RESULTS_FILE}.txt
# ---
# doc: Input variable
# PULL_REQUESTS   # "cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116"
# RELEASE_FORMAT  # CMSSW_10_4_X_2018-11-26-2300
# PULL_REQUEST    # CMSSW PR number, should avoid
# CMSDIST_PR      # CMSDIST PR number, should avoid
# ARCHITECTURE    # architecture (ex. slc6_amd64_gcc700)
# and some others
export CMSSW_GIT_REFERENCE=/cvmfs/cms.cern.ch/cmssw.git.daily
source ${PR_TESTING_DIR}/_helper_functions.sh   # general helper functions
source ${CMS_BOT_DIR}/jenkins-artifacts
source ${COMMON}/github_reports.sh
NCPU=$(${COMMON}/get_cpu_number.sh)
if [[  $NODE_NAME == *"cms-cmpwg-0"* ]]; then
   let NCPU=${NCPU}/2
fi
let NCPU2=${NCPU}*2

function prepare_upload_results (){
    cd $WORKSPACE
    if [ -d ${WORKSPACE}/upload ] ; then
      for ut in $(find $WORKSPACE/upload -mindepth 1 -maxdepth 1 -name '*' -type d | sed 's|.*/||') ; do
        UT_STATUS="OK"
        if [ -f $WORKSPACE/upload/${ut}/status ] ; then UT_STATUS=$(cat $WORKSPACE/upload/${ut}/status) ; fi
        echo "USER_TEST_${ul};${UT_STATUS},User Test ${ut},See Log,${ut}" >> ${RESULTS_FILE}/${ut}.txt
      done
    else
      mkdir -p upload
    fi
    for f in testsResults build-logs clang-logs runTheMatrix-results llvm-analysis *.log *.html *.txt *.js DQMTestsResults valgrindResults-* cfg-viewerResults igprof-results-data git-merge-result git-log-recent-commits addOnTests codeRules dupDict material-budget ; do
      [ -e $f ] && mv $f upload/$f
    done
    if [ -e upload/renderPRTests.js ] ; then mkdir -p upload/js && mv upload/renderPRTests.js upload/js/ ; fi
    if [ -e upload/matrixTests.log  ] ; then mkdir -p upload/runTheMatrix-results && mv upload/matrixTests.log upload/runTheMatrix-results/ ; fi
    if [ -d upload/addOnTests       ] ; then find upload/addOnTests -name '*.root' -type f | xargs rm -f ; fi
    echo "Preparation done"

    # for uploading CMSDIST build logs
    LOG_SRC="${WORKSPACE}/${BUILD_DIR}/BUILD/${ARCHITECTURE}"
    LOCAL_LOGDIR="${WORKSPACE}/upload"
    if [ -d "${LOG_SRC}" ] ; then
      [ -d ${WORKSPACE}/${BUILD_DIR}/DEPS ] && mv ${WORKSPACE}/${BUILD_DIR}/DEPS ${WORKSPACE}/upload/DEPS
      pushd ${LOG_SRC}
        for log in $(find . -maxdepth 4 -mindepth 4 -name log -type f | sed 's|^./||') ; do
          dir=$(dirname $log)
          mkdir -p ${LOCAL_LOGDIR}/${dir}
          mv $log ${LOCAL_LOGDIR}/${dir}/
          [ -e ${dir}/src-logs.tgz ] && mv ${dir}/src-logs.tgz ${LOCAL_LOGDIR}/${dir}/
          json=$(basename $(dirname $dir)).json
          [ -e "${dir}/${json}" ] && mv ${dir}/${json} ${LOCAL_LOGDIR}/${dir}/
          [ -e "${dir}/opts.json" ] && mv ${dir}/opts.json ${LOCAL_LOGDIR}/${dir}/
        done
      popd
    fi
}

function prepare_upload_comment_exit(){
    prepare_upload_results
    if [ -z ${NO_POST} ]; then
        send_jenkins_artifacts ${WORKSPACE}/upload pull-request-integration/PR-${REPORT_H_CODE}/${BUILD_NUMBER}
    fi
    report_pull_request_results_all_prs_with_commit $@ --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} ${NO_POST}
    exit 0
}

# ----------
# -- MAIN --
# ----------
echo_section "Variable setup"

# Seperate script use different flag in order not to comment back to Github
NO_POST=
DRY_RUN=
if [ "X$AUTO_POST_MESSAGE" != Xtrue ]; then
  NO_POST='--no-post'
  DRY_RUN='--dry-run'
fi
export NO_POST ; export DRY_RUN
export PYTHONPATH=$CMS_BOT_DIR:$PYTHONPATH

# If RELEASE_FORMAT is not set, use the CMSSW_DEVEL_BRANCH.
# if someone starts jenkins job without scheduler directly from Jenkins
IS_DEV_BRANCH=false
DEV_BRANCH=$(grep '^ *CMSSW_DEVEL_BRANCH *= *' $CMS_BOT_DIR/releases.py | sed 's| ||g;s|.*=||;s|"||g')
if [ -z ${RELEASE_FORMAT} ]; then
     RELEASE_FORMAT=$DEV_BRANCH
fi

CMSSW_QUEUE=$(echo ${RELEASE_FORMAT} | sed 's/_X.*/_X/')  # RELEASE_FORMAT - CMSSW_10_4_X_2018-11-26-2300
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | tr ',' ' ' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//' )  # to make consistent separation in list
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )  # Repos without pull number
fail_if_empty "${UNIQ_REPOS}" "UNIQ_REPOS"
UNIQ_REPO_NAMES=$(echo ${UNIQ_REPOS} | tr ' ' '\n' | sed 's|.*/||' )
UNIQ_REPO_NAMES_WITH_COUNT=$(echo ${UNIQ_REPO_NAMES} | sort | uniq -c )
REPORT_H_CODE=$(echo ${PULL_REQUESTS} | tr ',' '\n' | sort | md5sum | sed 's| .*||' | cut -c27-33)      # Used to to create link to folder where uploaded files are.
RPM_UPLOAD_REPO=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep -v '/cmssw#' | grep -v '/cms-bot#' | sort | uniq | md5sum | sed 's| .*||')

let WEEK_NUM=$(tail -1 $CMS_BOT_DIR/ib-weeks | sed 's|.*-||;s|^0*||')%2 || true
CMS_WEEKLY_REPO=cms.week${WEEK_NUM}
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
export JENKINS_PREFIX

# this is to automount directories in cvmfs, otherwise they wont show up
ls /cvmfs/cms.cern.ch
ls /cvmfs/cms-ib.cern.ch || true

which scram 2>/dev/null || source /cvmfs/cms.cern.ch/cmsset_default.sh

echo_section "Pull request checks"
# Check if same organization/repo PRs
if [ $(echo ${UNIQ_REPO_NAMES_WITH_COUNT}  | grep -v '1 ' | wc -w ) -gt 0 ]; then
    exit_with_comment_failure_main_pr  ${DRY_RUN} -m "ERROR: multiple PRs from different organisations but same repos:    ${UNIQ_REPO_NAMES_WITH_COUNT}"
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
        exit_with_comment_failure_main_pr  ${DRY_RUN} -m  "ERROR: PRs for  repo '${U_REPO}' wants to merge to different branches: ${UNIQ_MASTERS}"
    fi
done

CMSDIST_PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep '/cmsdist#' | head -n 1) # get 1st one
CMSSW_PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep '/cmssw#' | head -n 1)
CMSDIST_TAG=  # To make sure no one set to different value by accident.
if [ ! -z ${CMSDIST_PR} ] ; then
    CMSDIST_TAG=$(get_base_branch "$CMSDIST_PR" )
fi
if [[ ! -z ${CMSSW_PR} ]] ; then
    CMSSW_BR=$(get_base_branch $CMSSW_PR)
fi
CONFIG_LINE=$(${COMMON}/get_config_map_line.sh  "${CMSSW_QUEUE-$CMSSW_BR}" "$CMSDIST_TAG" "${ARCHITECTURE}")
fail_if_empty "${CONFIG_LINE}"

export CMSDIST_TAG=$(echo ${CONFIG_LINE} | sed 's/^.*CMSDIST_TAG=//' | sed 's/;.*//')

if [ -z ${ARCHITECTURE} ] ; then
    ARCHITECTURE=$(echo ${CONFIG_LINE} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )
fi
export SCRAM_ARCH=${ARCHITECTURE}

# Put hashcodes of last commits to a file. Mostly used for commenting back
rm -rf ${WORKSPACE}/prs_commits.txt
touch ${WORKSPACE}/prs_commits.txt
for PR in ${PULL_REQUESTS}; do
    PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    COMMIT=$(${CMS_BOT_DIR}/process-pull-request -c -r ${PR_NAME_AND_REPO} ${PR_NR})
    echo ${COMMIT} | sed 's|.* ||' > "$(get_path_to_pr_metadata ${PR})/COMMIT"
    echo "${PR}=${COMMIT}" >> ${WORKSPACE}/prs_commits.txt
done

mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d 'Setting up build environment' || true

COMP_QUEUE=
case $CMSSW_QUEUE in
  CMSSW_9_4_MAOD_X*|CMSSW_9_4_AN_X* ) COMP_QUEUE=$CMSSW_QUEUE ;;
  * ) COMP_QUEUE=$(echo $CMSSW_QUEUE | cut -d_ -f1-3)_X;;
esac
if [ "X$DEV_BRANCH" = "X$COMP_QUEUE" ] ; then IS_DEV_BRANCH=true ; fi

REAL_ARCH=-`cat /proc/cpuinfo | grep vendor_id | head -n 1 | sed "s/.*: //"`
CMSSW_IB=  # We are getting CMSSW_IB, so that we wont rebuild all the software
COMPARISON_REL=
if [[ $RELEASE_FORMAT != *-* ]]; then
    COMP_ARCH=$COMPARISON_ARCH
    if [ "X$COMP_ARCH" = "X" ] ; then
      COMP_ARCH=$(cat $CONFIG_MAP | grep "=$COMP_QUEUE;" | grep -v "DISABLED=1" | grep "SCRAM_ARCH=${ARCHITECTURE};" | grep "ADDITIONAL_TESTS=.*baseline" | sed 's|^.*SCRAM_ARCH=||;s|;.*$||')
      if [ "X$COMP_ARCH" = "X" ] ; then
        COMP_ARCH=$(cat $CONFIG_MAP | grep $COMP_QUEUE | grep -v "DISABLED=1" | grep "ADDITIONAL_TESTS=.*baseline" | sed 's|^.*SCRAM_ARCH=||;s|;.*$||')
        if [ "X$COMP_ARCH" = "X" ] ; then COMP_ARCH=$ARCHITECTURE ; fi
      fi
    fi
    for SCRAM_REL in $(scram -a $SCRAM_ARCH l -c $RELEASE_FORMAT | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" |  awk '{print $2":"$3}' | sort -r | sed 's|:.*$||') ;  do
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
    if [ "X$CMSSW_IB" = "X" ] ; then
      CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $CMSSW_QUEUE | grep -v -f "$CMS_BOT_DIR/ignore-releases-for-tests" | awk '{print $2}' | sort -r | head -1)
      if [ "X$CMSSW_IB" = "X" ] ; then
        report_pull_request_results_all_prs_with_commit "RELEASE_NOT_FOUND" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} ${NO_POST}
        mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d 'Unable to find CMSSW release for ${CMSSW_QUEUE}/${SCRAM_ARCH}' || true
        exit 0
      fi
      COMPARISON_ARCH=$ARCHITECTURE
      COMPARISON_REL=$CMSSW_IB
    fi
else
  CMSSW_IB=$RELEASE_FORMAT
  COMPARISON_ARCH=$ARCHITECTURE
  COMPARISON_REL=$CMSSW_IB
fi

PKG_TOOL_BRANCH=$(echo ${CONFIG_LINE} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )
PKG_TOOL_VERSION=$(echo ${PKG_TOOL_BRANCH} | cut -d- -f 2)
if [[ ${PKG_TOOL_VERSION} -lt 32 && ! -z $(echo ${UNIQ_REPO_NAMES} | tr ' ' '\n' | grep -v -w cmssw | grep -v -w cmsdist | grep -v -w cms-bot ) ]] ; then
    # If low version and but there are external repos to test, fail
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Invalid PKGTOOLS version to test external packages." || true
    exit_with_comment_failure_main_pr ${DRY_RUN} -m "ERROR: RELEASE_FORMAT ${CMSSW_QUEUE} uses PKG_TOOL_BRANCH ${PKG_TOOL_BRANCH} which is lower then required to test externals."
fi

# Do git pull --rebase for each PR except for /cmssw
for U_REPO in $(echo ${UNIQ_REPOS} | tr ' ' '\n'  | grep -v '/cmssw' ); do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        ERR=false
        git_clone_and_merge "$(get_cached_GH_JSON "${PR}")" || ERR=true
        if ${ERR} ; then
            mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Failed to merge ${PR}" || true
            exit_with_comment_failure_main_pr  ${DRY_RUN} -m "ERROR: failed to merge ${PR} PR"
        fi
    done
done

# Preparations depending on from repo type
CMSSW_ORG='cms-sw'
BUILD_EXTERNAL=false
CMSDIST_ONLY=true # asume cmsdist only
CHECK_HEADER_TESTS=false
for U_REPO in ${UNIQ_REPOS}; do
    PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
    PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
    case "$PKG_NAME" in  # We do not care where the repo is kept (ex. cmssw organisation or other)
	cmssw)
          CMSSW_ORG=$(echo ${PKG_REPO} | sed 's|/.*||')
          CMSDIST_ONLY=false
          CHECK_HEADER_TESTS=true
	;;
        cms-bot)
          # do nothing
	;;
	cmsdist|pkgtools)
	  BUILD_EXTERNAL=true
	;;
	*)
	  PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
	  SPEC_NAMES=$( ${CMS_BOT_DIR}/pr_testing/get_external_name.sh ${PKG_REPO} )
	  BUILD_EXTERNAL=true
          for SPEC_NAME in ${SPEC_NAMES} ; do
	    if ! ${PR_TESTING_DIR}/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$SPEC_NAME" "$CMSSW_QUEUE" "$ARCHITECTURE" "${CMS_WEEKLY_REPO}" "${BUILD_DIR}" ; then
              mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Error getting source flag for ${PKG_REPO}, fix spec ${SPEC_NAME}" || true
	      exit_with_comment_failure_main_pr ${DRY_RUN} -m "ERROR: There was an issue generating parameters for
	        cmsBuild '--source' flag for spec file ${SPEC_NAME} from ${PKG_REPO} repo."
            fi
          done
	;;
	esac
done

# modify comments that test are being triggered by Jenkins
modify_comment_all_prs "- ${CMSSW_IB}/${SCRAM_ARCH}: "

# Notify github that the script will start testing now
report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} ${NO_POST}

# Prepera html templates
cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js

mkdir ${RESULTS_FILE}
touch ${RESULTS_FILE}.txt ${RESULTS_FILE}/comparison.txt
echo "PR_NUMBERS;$PULL_REQUESTS" >> ${RESULTS_FILE}.txt
echo 'BASE_IB;'$CMSSW_IB >> ${RESULTS_FILE}.txt
echo 'BUILD_NUMBER;'$BUILD_NUMBER >> ${RESULTS_FILE}.txt
echo "PR_NUMBER;$REPORT_H_CODE" >> ${RESULTS_FILE}.txt
if [ "X$COMPARISON_REL" == "X" ] ; then
  echo "COMPARISON_IB;$BASE_IB" >> ${RESULTS_FILE}.txt
else
  echo "COMPARISON_IB;$COMPARISON_REL" >> ${RESULTS_FILE}.txt
fi

if ${BUILD_EXTERNAL} ; then
    mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d "Building CMSSW externals" || true
    if [ ! -d "pkgtools" ] ; then
        git clone git@github.com:cms-sw/pkgtools -b $PKG_TOOL_BRANCH
    fi
    if [ ! -d "cmsdist" ] ; then
        git clone git@github.com:cms-sw/cmsdist -b $CMSDIST_TAG
    fi

    echo_section "Building, testing and commenting status to github"
    # add special flags for pkgtools/cmsbuild if version is high enough
    REF_REPO=
    SOURCE_FLAG=
    if [ "X$USE_CMSPKG_REFERENCE" = "Xtrue" ] ; then
      if [ ${PKG_TOOL_VERSION} -gt 31 ] ; then
        REF_REPO="--reference "$(readlink /cvmfs/cms-ib.cern.ch/$(echo $CMS_WEEKLY_REPO | sed 's|^cms.||'))
        if [ -e ${WORKSPACE}/get_source_flag_result.txt ] ; then
          SOURCE_FLAG=$(cat ${WORKSPACE}/get_source_flag_result.txt )
        fi
      fi
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
    CMSBUILD_ARGS="--tag ${REPORT_H_CODE}"
    if [ ${PKG_TOOL_VERSION} -gt 31 ] ; then
      CMSBUILD_ARGS="${CMSBUILD_ARGS} --monitor --log-deps --force-tag --tag hash --delete-build-directory --link-parent-repository"
    fi
    PKGS="cms-common cms-git-tools cmssw-tool-conf"
    COMPILATION_CMD="PYTHONPATH= ./pkgtools/cmsBuild --server http://${CMSREP_IB_SERVER}/cgi-bin/cmspkg --upload-server ${CMSREP_IB_SERVER} \
        ${CMSBUILD_ARGS} --builders 3 -i $WORKSPACE/$BUILD_DIR $REF_REPO \
        $SOURCE_FLAG --arch $ARCHITECTURE -j ${NCPU}"
    TMP_REPO="PR_$(echo ${RPM_UPLOAD_REPO}_${CMSSW_QUEUE}_${ARCHITECTURE} | md5sum | sed 's| .*||' | tail -c 9)"
    UPLOAD_OPTS="--upload-tmp-repository ${TMP_REPO}"
    if [ $(curl -s --head http://${CMSREP_IB_SERVER}/cmssw/repos/${CMS_WEEKLY_REPO}.${TMP_REPO}/${ARCHITECTURE}/latest/ 2>&1 | head -1 | grep " 200 OK" |wc -l) -gt 0 ] ; then
      UPLOAD_OPTS="--sync-back"
      COMPILATION_CMD="${COMPILATION_CMD} --repository ${CMS_WEEKLY_REPO}.${TMP_REPO}"
    else
      COMPILATION_CMD="${COMPILATION_CMD} --repository ${CMS_WEEKLY_REPO}"
    fi
    if [ "${SOURCE_FLAG}" != "" ] ; then UPLOAD_OPTS="${UPLOAD_OPTS} --force-upload" ; fi
    echo $COMPILATION_CMD build ${PKGS} > ${WORKSPACE}/cmsswtoolconf.log  # log the command to be run
    # run the command and both log it to file and display it
    (eval $COMPILATION_CMD build ${PKGS} && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
    echo_section 'END OF BUILD LOG'

    TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
    GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true

    #upload packages build
    BLD_PKGS=$(ls $WORKSPACE/$BUILD_DIR/RPMS/${ARCHITECTURE}/ | grep '.rpm$' | cut -d+ -f2 | grep -v 'coral-debug' || true)
    if [ "${BLD_PKGS}" != "" ] ; then eval $COMPILATION_CMD ${UPLOAD_OPTS} upload ${BLD_PKGS} ; fi
    for d in bootstraptmp tmp RPMS SOURCES  SPECS  SRPMS WEB ; do
      rm -rf $WORKSPACE/$BUILD_DIR/${d} || true
    done

    echo 'CMSSWTOOLCONF_LOGS;OK,External Build Logs,See Log,.' >> ${RESULTS_FILE}/toolconf.txt
    if [ "X$TEST_ERRORS" != X ] || [ "X$GENERAL_ERRORS" == X ]; then
      echo 'CMSSWTOOLCONF_RESULTS;ERROR,Externals compilation,See Log,cmsswtoolconf.log' >> ${RESULTS_FILE}/toolconf.txt
      mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Failed to build externals" || true
      prepare_upload_comment_exit "PARSE_BUILD_FAIL" --unit-tests-file $WORKSPACE/upload/cmsswtoolconf.log
    else
      echo 'CMSSWTOOLCONF_RESULTS;OK,Externals compilation,See Log,cmsswtoolconf.log' >> ${RESULTS_FILE}/toolconf.txt
    fi

    # Create an appropriate CMSSW area
    source $WORKSPACE/$BUILD_DIR/cmsset_default.sh
    echo /cvmfs/cms.cern.ch > $WORKSPACE/$BUILD_DIR/etc/scramrc/links.db
    scram -a $SCRAM_ARCH project $CMSSW_IB

    # To make sure we always pick scram from local area
    rm -f $CMSSW_IB/config/scram_basedir
    ls $WORKSPACE/$BUILD_DIR/share/lcg/SCRAMV1 > $CMSSW_IB/config/scram_version
    config_tag=$(grep '%define *configtag *V' $WORKSPACE/cmsdist/scram-project-build.file | sed 's|.*configtag *V|V|;s| *||g')
    if [ "$(cat $CMSSW_IB/config/config_tag)" != "${config_tag}" ] ; then
      git clone git@github.com:cms-sw/cmssw-config scram-buildrules
      pushd scram-buildrules
        git checkout ${config_tag}
      popd
      echo ${config_tag} > $WORKSPACE/$CMSSW_IB/config/config_tag
      mv $CMSSW_IB/config/SCRAM $CMSSW_IB/config/SCRAM.orig
      mv scram-buildrules/SCRAM $CMSSW_IB/config/SCRAM
      if [ -d scram-buildrules/Projects/CMSSW ] ; then
        cp -f scram-buildrules/Projects/CMSSW/BuildFile.xml $CMSSW_IB/config/BuildFile.xml
        cp -f scram-buildrules/Projects/CMSSW/SCRAM_ExtraBuildRule.pm $CMSSW_IB/config/SCRAM_ExtraBuildRule.pm
      else
        cp -f scram-buildrules/CMSSW_BuildFile.xml $CMSSW_IB/config/BuildFile.xml
        cp -f scram-buildrules/CMSSW_SCRAM_ExtraBuildRule.pm $CMSSW_IB/config/SCRAM_ExtraBuildRule.pm
      fi
      if [ -f $CMSSW_IB/config/SCRAM.orig/GMake/CXXModules.mk ] ; then
        cp $WORKSPACE/cmsdist/CXXModules.mk.file $CMSSW_IB/config/SCRAM/GMake/CXXModules.mk
      fi
    fi
    rm -rf scram-buildrules
    cd $WORKSPACE/$CMSSW_IB/src
    touch $WORKSPACE/cmsswtoolconf.log
    CTOOLS=$WORKSPACE/$CMSSW_IB/config/toolbox/${ARCHITECTURE}/tools/selected
    BTOOLS=${CTOOLS}.backup
    mv ${CTOOLS} ${BTOOLS}
    TOOL_CONF_VERSION=$(ls -d $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/* | sed 's|.*/||')
    echo "${CMS_WEEKLY_REPO}.${TMP_REPO}/${TOOL_CONF_VERSION}" > $WORKSPACE/cmssw-tool-conf.txt
    echo "CMSSWTOOLCONF_VERSION;OK,External tool conf,See log,cmssw-tool-conf.txt" >> ${RESULTS_FILE}/toolconf.txt
    mv $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/${TOOL_CONF_VERSION}/tools/selected ${CTOOLS}

    #Generate External Tools Status
    echo '<html><head><link href="https://netdna.bootstrapcdn.com/bootstrap/3.1.1/css/bootstrap.min.css" rel="stylesheet"></head>' > $WORKSPACE/upload/external-tools.html
    echo '<body><h2>External tools build Statistics</h2><br/><table class="table table-striped"><tr><td>Tool Name</td><td>#Files(new)</td><td>#Files(old)</td><td>Size(new)</td><td>Size(old)</td></tr>' >> $WORKSPACE/upload/external-tools.html
    for pkg in $(find ${WORKSPACE}/${BUILD_DIR}/BUILD/${ARCHITECTURE} -maxdepth 3 -mindepth 3 -type d | sed "s|$WORKSPACE/$BUILD_DIR/BUILD/||" | sort) ; do
      ltpath="${WORKSPACE}/${BUILD_DIR}/${pkg}"
      [ -d ${ltpath} ] || continue
      l_tc=$(find ${ltpath} -follow | wc -l)
      l_ts=$(du -shL ${ltpath} | awk '{print $1}')
      tdir=$(dirname $pkg)
      rtpath=$(grep -R ${tdir} ${BTOOLS} | grep '_BASE\|CMSSW_SEARCH_PATH' | tail -1 | sed 's|.* default="||;s|".*||')
      if [ "${rtpath}" = "" ] || [ ! -d "${rtpath}" ] ; then
        r_tc=0
        r_ts=0
      else
        r_tc=$(find ${rtpath} -follow | wc -l)
        r_ts=$(du -shL ${rtpath} | awk '{print $1}')
      fi
      tool=$(basename $tdir)
      echo "<tr><td>${tool}</td><td>$l_tc</td><td>$r_tc</td><td>$l_ts</td><td>$r_ts</td></tr>" >> $WORKSPACE/upload/external-tools.html
    done
    echo "</table></body></html>" >> $WORKSPACE/upload/external-tools.html
    echo 'CMSSWTOOLCONF_STATS;OK,External Build Stats,See Log,external-tools.html' >> ${RESULTS_FILE}/toolconf.txt

    if [ "X$BUILD_FULL_CMSSW" != "Xtrue" ] ; then
      # Setup all the toolfiles previously built
      DEP_NAMES=
      if [ -e "${BTOOLS}/cmssw.xml" ] ; then cp ${BTOOLS}/cmssw.xml ${CTOOLS}/cmssw.xml ; fi
      RMV_CMSSW_EXTERNAL="$(ls -d $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/*-remove-release-external-lib 2>/dev/null || true)"
      if [ "${RMV_CMSSW_EXTERNAL}" != "" ] ; then
        chmod +x ${RMV_CMSSW_EXTERNAL}
      fi
      for xml in $(ls ${CTOOLS}/*.xml) ; do
        name=$(basename $xml)
        tool=$(echo $name | sed 's|.xml$||')
        echo "Checking tool $tool ($xml)"
        if [ ! -e ${BTOOLS}/$name ] ; then
          scram setup $xml
          continue
        fi
        nver=$(grep '<tool ' $xml          | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
        over=$(grep '<tool ' ${BTOOLS}/$name | tr ' ' '\n' | grep 'version=' | sed 's|version="||;s|".*||g')
        echo "Checking version in release: $over vs $nver"
        if [ "$nver" = "$over" ] ; then continue ; fi
        echo "Settings up $name: $over vs $nver"
        DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
      done
      sed -i -e 's|.*/lib/python2.7/site-packages" .*||;s|.*/lib/python3.6/site-packages" .*||' ../config/Self.xml
      touch $CTOOLS/*.xml
      scram setup
      scram setup self
      rm -rf $WORKSPACE/$CMSSW_IB/external
      scram build -r echo_CXX 
      if [ "${DEP_NAMES}" != "" ] ; then
        CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
      fi
    else
      rm -f $WORKSPACE/$CMSSW_IB/.SCRAM/$ARCHITECTURE/Environment
      touch $CTOOLS/*.xml
      scram setup self
      scram setup
      scram tool remove cmssw || true
      rm -rf $WORKSPACE/$CMSSW_IB/external
      scram build -r echo_CXX 
      CMSSW_DEP="*"
    fi
    set +x ; eval $(scram runtime -sh) ; set -x
    echo $LD_LIBRARY_PATH
    if [ -e $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/00-nvidia-drivers ] ; then
      SCRAM=scram bash -ex $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/00-nvidia-drivers || true
    fi
    if [ "$CMSSW_DEP" = "" ] ; then CMSSW_DEP="FWCore/Version" ; fi
    git cms-addpkg --ssh "$CMSSW_DEP" 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
    rm -rf $WORKSPACE/$CMSSW_IB/external
    scram b clean
    scram b -r echo_CXX
fi # end of build external
echo_section "end of build external"

# This part responsible for testing CMSSW
echo_section "Testing CMSSW"
voms-proxy-init -voms cms -valid 24:00 || true  # To get access to jenkins artifact machine

DO_COMPARISON=true
DO_MB_COMPARISON=false
if [ "$TEST_CONTEXT" = "GPU" ] ; then
  APPLY_FIREWORKS_RULE=false
  TEST_CLANG_COMPILATION=false
  CODE_RULES=false
  CHECK_HEADER_TESTS=false
  DO_STATIC_CHECKS=false
  DQM_TESTS=false
  DO_DUPLICATE_CHECKS=false
  DO_ADDON_TESTS=false
  RUN_CONFIG_VIEWER=false
  DO_COMPARISON=false
  DO_ADDON_TESTS=false
  DO_MB_COMPARISON=false
  WORKFLOWS_FOR_VALGRIND_TEST=""
fi

### to know at the end of the tests if everything went ok
ALL_OK=true
BUILD_OK=true
UNIT_TESTS_OK=true
RELVALS_OK=true
ADDON_OK=true
CLANG_BUILD_OK=true
PYTHON3_BUILD_OK=true
RUN_TESTS=true
USE_DAS_SORT=YES

has_jenkins_artifacts ib-baseline-tests/$COMPARISON_REL/$COMPARISON_ARCH/$REAL_ARCH/matrix-results/used-ibeos-sort || USE_DAS_SORT=NO

cd $WORKSPACE
if [ ! -d CMSSW_* ]; then  # if no directory that starts with "CMSSW_" exist, then bootstrap with SCRAM
  scram -a $SCRAM_ARCH  project $CMSSW_IB
fi
cd $WORKSPACE/$CMSSW_IB

sed -i -e 's|^define  *processTmpMMDData.*|processTmpMMDData=true\ndefine processTmpMMDDataXX|;s|^define  *processMMDData.*|processMMDData=true\ndefine processMMDDataXX|' config/SCRAM/GMake/Makefile.rules
set +x
eval $(scram run -sh)
set -x
echo $LD_LIBRARY_PATH | tr ':' '\n'
BUILD_LOG_DIR="${CMSSW_BASE}/tmp/${SCRAM_ARCH}/cache/log"
ANALOG_CMD="scram build outputlog && ($CMS_BOT_DIR/buildLogAnalyzer.py --logDir ${BUILD_LOG_DIR}/src || true)"
report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Test started: $CMSSW_IB for $SCRAM_ARCH" ${NO_POST}

cd $WORKSPACE/$CMSSW_IB/src
git config --global --replace-all merge.renamelimit 2500 || true

GIT_MERGE_RESULT_FILE=$WORKSPACE/git-merge-result
RECENT_COMMITS_FILE=$WORKSPACE/git-recent-commits.json
echo '{}' > $RECENT_COMMITS_FILE
# use the branch name if necesary
if ! $CMSDIST_ONLY ; then # If a CMSSW specific PR was specified #
  # this is to test several pull requests at the same time
  for PR in $( echo ${PULL_REQUESTS} | tr ' ' '\n' | grep "/cmssw#"); do
    echo 'I will add the following pull request to the test'
    PR_NR=$(echo ${PR} | sed 's/.*#//' )
    (git cms-merge-topic --debug --ssh -u ${CMSSW_ORG}:${PR_NR} && echo 'ALL_OK') 2>&1 | tee -a $GIT_MERGE_RESULT_FILE
  done

  if grep 'Automatic merge failed' $GIT_MERGE_RESULT_FILE; then
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Merge: Unable to merge CMSSW PRs" || true
    prepare_upload_comment_exit "NOT_MERGEABLE"
  fi

  if grep "Couldn't find remote ref" $GIT_MERGE_RESULT_FILE; then
    echo "Please add the branch name to the parameters"
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Merge: Unable to find remote reference." || true
    prepare_upload_comment_exit "REMOTE_REF_ISSUE"
  fi

  git diff --name-only $CMSSW_VERSION > $WORKSPACE/changed-files

  # look for any other error in general
  if ! grep "ALL_OK" $GIT_MERGE_RESULT_FILE; then
    echo "There was an error while running git cms-merge-topic"
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Merge: Unknow error while merging." || true
    prepare_upload_comment_exit "GIT_CMS_MERGE_TOPIC_ISSUE"
  fi

  #############################################
  # Check if there are unwanted commits that came with the merge.
  ############################################
  RECENT_COMMITS_LOG_FILE=$WORKSPACE/git-log-recent-commits

  if [ ! -d $WORKSPACE/cms-prs ]  ; then
    git clone --depth 1 git@github.com:cms-sw/cms-prs $WORKSPACE/cms-prs
  fi
  $SCRIPTPATH/get-merged-prs.py -s $CMSSW_VERSION -e HEAD -g $CMSSW_BASE/src/.git -c $WORKSPACE/cms-prs/cms-sw/cmssw -o $RECENT_COMMITS_FILE
  git log ${CMSSW_IB}..HEAD --merges 2>&1      | tee -a $RECENT_COMMITS_LOG_FILE
  if [ $DO_MB_COMPARISON -a $(grep 'Geometry' $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
    has_jenkins_artifacts material-budget/$CMSSW_IB/$SCRAM_ARCH/Images || DO_MB_COMPARISON=false
  else
    DO_MB_COMPARISON=false
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
  # report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --pr-job-id ${BUILD_NUMBER} ${NO_POST}
  git log --oneline --merges ${CMSSW_VERSION}..
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Compiling" ${NO_POST}
fi

# #############################################
# test compilation with Clang
# ############################################
echo 'test clang compilation'

NEED_CLANG_TEST=false
if cat $CONFIG_MAP | grep $CMSSW_QUEUE | grep PRS_TEST_CLANG= | grep SCRAM_ARCH=$ARCHITECTURE; then
  NEED_CLANG_TEST=true
fi

if [ "X$TEST_CLANG_COMPILATION" = Xtrue -a $NEED_CLANG_TEST = true -a "X$CMSSW_PR" != X ]; then
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Testing Clang compilation" ${NO_POST}

  #first, add the command to the log
  CLANG_USER_CMD="USER_CUDA_FLAGS='--expt-relaxed-constexpr' USER_CXXFLAGS='-Wno-register -fsyntax-only' scram build -k -j ${NCPU2} COMPILER='llvm compile'"
  CLANG_CMD="scram b vclean && ${CLANG_USER_CMD} BUILD_LOG=yes"
  echo $CLANG_USER_CMD > $WORKSPACE/buildClang.log

  (eval $CLANG_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/buildClang.log
  (eval ${ANALOG_CMD}) 2>&1 | tee -a $WORKSPACE/buildClang.log

  TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/buildClang.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/buildClang.log` || true
  for i in $(grep ": warning: " $WORKSPACE/buildClang.log | grep "/$CMSSW_IB/" | sed "s|.*/$CMSSW_IB/src/||;s|:.*||;s| ||g" | sort -u) ; do
    if [ $(grep "$i" $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
      echo $i >> $WORKSPACE/clang-new-warnings.log
      grep ": warning: " $WORKSPACE/buildClang.log | grep "/$i" >> $WORKSPACE/clang-new-warnings.log
    fi
  done
  if [ -e $WORKSPACE/clang-new-warnings.log ]  ; then
    echo 'CLANG_NEW_WARNINGS;ERROR,Clang Warnings to fix,See Log,clang-new-warnings.log' >> ${RESULTS_FILE}/clang.txt
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^CLANG-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      CLANG_BUILD_OK=false
      mark_commit_status_all_prs 'clang' 'error' -u "${BUILD_URL}" -d "Found build warnings." || true
    fi
  fi

  if [ -d ${BUILD_LOG_DIR}/html ] ; then
    mv ${BUILD_LOG_DIR}/html $WORKSPACE/clang-logs
    echo 'CLANG_LOG;OK,Clang warnings summary,See Log,clang-logs' >> ${RESULTS_FILE}/clang.txt
  fi
  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when testing compilation with clang"
    echo 'CLANG_COMPILATION_RESULTS;ERROR,Clang Compilation,See Log,buildClang.log' >> ${RESULTS_FILE}/clang.txt
    RUN_TESTS=false
    ALL_OK=false
    CLANG_BUILD_OK=false
    mark_commit_status_all_prs 'clang' 'error' -u "${BUILD_URL}" -d "Found build errors." || true
  else
    echo "the clang compilation had no errors/warnings!!"
    echo 'CLANG_COMPILATION_RESULTS;OK,Clang Compilation,See Log,buildClang.log' >> ${RESULTS_FILE}/clang.txt
  fi
fi

#Do QA checks
#Code Rules
QA_RES="NOTRUN"
if [ "X$CMSDIST_ONLY" == "Xfalse" -a "X${CODE_RULES}" = "Xtrue" ]; then # If a CMSSW specific PR was specified
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Code Rules Checks" ${NO_POST}
  mkdir $WORKSPACE/codeRules
  cmsCodeRulesChecker.py -s $WORKSPACE/codeRules -r 1,3 || true
  QA_RES="OK"
  for r in $(find $WORKSPACE/codeRules -name 'cmsCodeRule*.txt' -type f) ; do
    QA_COUNT=$(grep '^/' $r | sed 's|^/||' | sort | uniq | xargs -i grep '{}' $WORKSPACE/changed-files  | wc -l)
    if [ "X$QA_COUNT" = "X0" ] ; then
      rm -f $r
    else
      CRULE=$(echo $r | sed 's|.*/cmsCodeRule||;s|.txt$||')
      echo "Rule$CRULE $description: https://raw.githubusercontent.com/${CMSSW_ORG}/cmssw/master/Utilities/ReleaseScripts/python/cmsCodeRules/config.py" > $r.new
      python -c "from Utilities.ReleaseScripts.cmsCodeRules.config import Configuration as x;print x['$CRULE']['description']" >> $r.new
      echo "" >> $r.new
      cat $r >> $r.new
      mv $r.new $r
      QA_RES="ERROR"
    fi
  done
  echo "CODE_RULES;${QA_RES},CMSSW Code Rules,See Logs,codeRules" >> ${RESULTS_FILE}/coderules.txt
fi

#Do Python3 checks
if $IS_DEV_BRANCH ; then
  PYTHON3_RES="OK"
  CMD_python=$(which python3) scram b -r -k -j ${NCPU} CompilePython > $WORKSPACE/python3.log 2>&1 || true
  if [ $(grep ' Error compiling ' $WORKSPACE/python3.log | wc -l) -gt 0 ] ; then
    PYTHON3_RES="ERROR"
    PYTHON3_BUILD_OK=false
    RUN_TESTS=false
    ALL_OK=false
    mark_commit_status_all_prs 'python3' 'error' -u "${BUILD_URL}" -d "Compilation errors" || true
  fi
  echo "PYTHON3_CHECKS;${PYTHON3_RES},Python3 Checks,See Log,python3.log" >> ${RESULTS_FILE}/python3.txt
fi

#
# Static checks
#
if [ "X$DO_STATIC_CHECKS" = "Xtrue" -a "$ONLY_FIREWORKS" = false -a "X$CMSSW_PR" != X -a "$RUN_TESTS" = "true" ]; then
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Static Checks" ${NO_POST}
  echo 'STATIC_CHECKS;OK,Static checks outputs,See Static Checks,llvm-analysis' >> ${RESULTS_FILE}/static.txt
  echo '--------------------------------------'
  pushd $WORKSPACE/$CMSSW_IB
  git cms-addpkg --ssh Utilities/StaticAnalyzers
  mkdir $WORKSPACE/llvm-analysis
  USER_CXXFLAGS='-Wno-register -DEDM_ML_DEBUG -w' SCRAM_IGNORE_PACKAGES="Fireworks/% Utilities/StaticAnalyzers" USER_LLVM_CHECKERS="-enable-checker threadsafety -enable-checker cms -disable-checker cms.FunctionDumper" \
    scram b -k -j ${NCPU2} checker SCRAM_IGNORE_SUBDIRS=test 2>&1 | tee -a $WORKSPACE/llvm-analysis/runStaticChecks.log
  cp -R $WORKSPACE/$CMSSW_IB/llvm-analysis/*/* $WORKSPACE/llvm-analysis || true
  if $IS_DEV_BRANCH && [ $(grep ': error: ' $WORKSPACE/llvm-analysis/runStaticChecks.log | wc -l) -gt 0 ] ; then
    echo "EDM_ML_DEBUG_CHECKS;ERROR,Static Check build log,See Log,llvm-analysis/runStaticChecks.log" >> ${RESULTS_FILE}/static.txt
  else
    echo "EDM_ML_DEBUG_CHECKS;OK,Static Check build log,See Log,llvm-analysis/runStaticChecks.log" >> ${RESULTS_FILE}/static.txt
  fi
  echo 'END OF STATIC CHECKS'
  echo '--------------------------------------'
  popd
fi

scram build clean
if [ "X$BUILD_FULL_CMSSW" != "Xtrue" -a -d $LOCALRT/src/.git ] ; then git cms-checkdeps -A -a || true; fi
CMSSW_PKG_COUNT=$(ls -d $LOCALRT/src/*/* | wc -l)
############################################
# Force the run of DQM tests if necessary
############################################
if [ "X$DQM_TESTS" = "Xtrue" ] ; then
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
CHK_HEADER_OK=true
if $IS_DEV_BRANCH ; then
  if [ "X${CHECK_HEADER_TESTS}" = "Xtrue" -a -f $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.chk_headers ] ; then
    report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running HeaderChecks" ${NO_POST}
    IGNORE_HDRS="%.i"
    if [ -e "$WORKSPACE/$RELEASE_FORMAT/src/TrackingTools/GsfTools/interface/MultiGaussianStateCombiner.h" ] ; then
      IGNORE_HDRS="TrackingTools/GsfTools/interface/MultiGaussianStateCombiner.h %.i"
    fi
    COMPILATION_CMD="scram b vclean && USER_CHECK_HEADERS_IGNORE='${IGNORE_HDRS}' scram build -k -j ${NCPU} check-headers"
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
      ALL_OK=false
      mark_commit_status_all_prs 'headers' 'error' -u "${BUILD_URL}" -d "Compilation errors" || true
    fi
    echo "HEADER_CHECKS;${CHK_HEADER_LOG_RES},Header Consistency,See Log,headers_chks.log" >> ${RESULTS_FILE}/header.txt
  fi
fi
# #############################################
# test compilation with GCC
# ############################################
if [ "X$EXTRA_CMSSW_PACKAGES" != "X" ] ; then
  git cms-addpkg $(echo "${EXTRA_CMSSW_PACKAGES}" | tr ',' ' ') || true
fi
mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d "Building CMSSW" || true
report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Compilation" ${NO_POST}
COMPILATION_CMD="scram b vclean && BUILD_LOG=yes scram b -k -j ${NCPU}"
if [ "$BUILD_EXTERNAL" = "true" -a $(grep '^edm_checks:' $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.rules | wc -l) -gt 0 ] ; then
  COMPILATION_CMD="scram b vclean && BUILD_LOG=yes SCRAM_NOEDM_CHECKS=yes scram b -k -j ${NCPU} && scram b -k -j ${NCPU} edm_checks"
fi
echo $COMPILATION_CMD > $WORKSPACE/build.log
(eval $COMPILATION_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/build.log
(eval ${ANALOG_CMD}) 2>&1 | tee -a $WORKSPACE/build.log
if [ -d ${BUILD_LOG_DIR}/html ] ; then mv ${BUILD_LOG_DIR}/html ${WORKSPACE}/build-logs ; fi
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/build.log` || true
GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/build.log` || true

for i in $(grep ": warning: " $WORKSPACE/build.log | grep "/$CMSSW_IB/" | sed "s|.*/$CMSSW_IB/src/||;s|:.*||;s| ||g" | sort -u) ; do
  if [ $(grep "$i" $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
    echo $i >> $WORKSPACE/new-build-warnings.log
    grep ": warning: " $WORKSPACE/build.log | grep "/$i" >> $WORKSPACE/new-build-warnings.log
  fi
done
if [ -e $WORKSPACE/new-build-warnings.log ]  ; then
    echo 'BUILD_NEW_WARNINGS;ERROR,Compilation Warnings to fix,See Log,new-build-warnings.log' >> ${RESULTS_FILE}/buildrules.txt
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^BUILD-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      BUILD_OK=false
      mark_commit_status_all_prs 'warnings' 'error' -u "${BUILD_URL}" -d "Found compilation warnings." || true
    fi
fi
BUILD_LOG_RES="ERROR"
if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when building"
    echo 'COMPILATION_RESULTS;ERROR,Compilation log,See Log,build.log' >> ${RESULTS_FILE}/build.txt
    RUN_TESTS=false
    ALL_OK=false
    BUILD_OK=false
    mark_commit_status_all_prs 'build' 'error' -u "${BUILD_URL}" -d "CMSSW compilation errors." || true
else
    echo "the build had no errors!!"
    echo 'COMPILATION_RESULTS;OK,Compilation log,See Log,build.log' >> ${RESULTS_FILE}/build.txt
    if [ -e ${WORKSPACE}/build-logs/index.html ] ; then
      if [ $(grep '<td> *[1-9][0-9]* *</td>' ${WORKSPACE}/build-logs/index.html  | grep -iv ' href' | grep -v 'ignoreWarning' | wc -l) -eq 0 ] ; then
        BUILD_LOG_RES="OK"
      fi
    elif [ ! -d ${BUILD_LOG_DIR}/src ] ; then
      BUILD_LOG_RES="OK"
    fi
    #Check Build Rule: Make sure nothing rebuilds after last build
    if [ $(cat $WORKSPACE/$CMSSW_IB/config/config_tag  | sed 's|V||;s|-||g;s|^0*||') -gt 50807 ] ; then
        scram build -f -j ${NCPU} -d  >${WORKSPACE}/scram-rebuild.log 2>&1
        grep ' newer ' ${WORKSPACE}/scram-rebuild.log | grep -v '/cache/xlibs.backup' > ${WORKSPACE}/newer-than-target.log || true
        if [ -s ${WORKSPACE}/newer-than-target.log ] ; then
            echo "SCRAM_REBUILD;ERROR,Build Rules,See Log,newer-than-target.log" >> ${RESULTS_FILE}/build.txt
            mark_commit_status_all_prs 'opt/buildrules' 'error' -u "${BUILD_URL}" -d "Build rules were re-executed." || true
        fi
    fi
fi
echo "BUILD_LOG;${BUILD_LOG_RES},Compilation warnings summary,See Logs,build-logs" >> ${RESULTS_FILE}/build.txt
mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d "Runnings tests" || true

#Work around for Simulation.so plugin
if [ -e $CMSSW_BASE/biglib/${SCRAM_ARCH}/Simulation.edmplugin ] ; then
  for p in SimDataFormatsValidationFormats_xr_rdict.pcm ; do
    if [ ! -e $CMSSW_BASE/biglib/${SCRAM_ARCH}/$p ] ; then
      for d in $CMSSW_RELEASE_BASE $CMSSW_FULL_RELEASE_BASE ; do
        if [ -e $d/biglib/${SCRAM_ARCH}/$p ] ; then
          ln -s $d/biglib/${SCRAM_ARCH}/$p $CMSSW_BASE/biglib/${SCRAM_ARCH}/$p
          break
        fi
      done
    fi
  done
fi

#Copy the cmssw ib das_client wrapper in PATH
cp -f $CMS_BOT_DIR/das-utils/das_client $CMS_BOT_DIR/das-utils/das_client.py
set +x ; eval $(scram run -sh) ;set -x
#Drop RELEASE_TOP/external/SCRAM_ARCH/data if LOCALTOP/external/SCRAM_ARCH/data exists
#to make sure external packages removed files are not picked up from release directory
if $BUILD_EXTERNAL ; then
  if [ "X${CMSSW_RELEASE_BASE}" != "X" ] ; then
    export CMSSW_SEARCH_PATH=$(echo $CMSSW_SEARCH_PATH | tr ':' '\n'  | grep -v "$CMSSW_RELEASE_BASE/external/" | tr '\n' ':')
    export LD_LIBRARY_PATH=$(echo $LD_LIBRARY_PATH | tr ':' '\n'  | grep -v "$CMSSW_RELEASE_BASE/external/" | tr '\n' ':')
  fi
fi
export PATH=$CMS_BOT_DIR/das-utils:$PATH
which das_client

[ "X$USE_DAS_SORT" = "XYES" ] && $CMS_BOT_DIR/das-utils/use-ibeos-sort

#Duplicate dict
QA_RES="NOTRUN"
if [ "X$DO_DUPLICATE_CHECKS" = Xtrue -a "$ONLY_FIREWORKS" = false -a "X$CMSDIST_ONLY" == "Xfalse" -a "$RUN_TESTS" = "true" ]; then
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Duplicate Dict Checks" ${NO_POST}
  mkdir $WORKSPACE/dupDict
  QA_RES="OK"
  for type in dup lostDefs edmPD ; do
    duplicateReflexLibrarySearch.py --${type} 2>&1 | grep -v ' SKIPPING ' > $WORKSPACE/dupDict/${type}.txt || true
  done
  QA_COUNT=$(cat $WORKSPACE/dupDict/dup.txt | grep '^  *[.]/[A-Z]' | grep '.xml' | sed 's|^  *./||' | sort | uniq | wc -l)
  if [ $QA_COUNT -gt 0 ] ; then QA_RES="ERROR" ; fi
  QA_COUNT=$(cat $WORKSPACE/dupDict/lostDefs.txt | grep '^[.]/[A-Z]' | grep '.xml' | sed 's|^./||' | sort | uniq | wc -l)
  if [ $QA_COUNT -gt 0 ] ; then  QA_RES="ERROR" ; fi
  if [ -s $WORKSPACE/dupDict/edmPD ] ; then QA_RES="ERROR" ; fi
  if [ "${QA_RES}" == "ERROR" ] ; then
    mark_commit_status_all_prs 'opt/dict' 'error' -u "${BUILD_URL}" -d "Duplicate dictionaries found" || true
  fi
  echo "DUPLICATE_DICT_RULES;${QA_RES},Duplicate Dictionaries,See Logs,dupDict" >> ${RESULTS_FILE}/qa.txt
fi

export CMS_PATH=/cvmfs/cms-ib.cern.ch
#
# Unit tests
#
if [ "X$DO_TESTS" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$RUN_TESTS" = "true" ]; then
  mark_commit_status_all_prs 'unittest' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Unit Tests" ${NO_POST}
  echo '--------------------------------------'
  UT_TIMEOUT=$(echo 7200+${CMSSW_PKG_COUNT}*20 | bc)
  UTESTS_CMD="timeout ${UT_TIMEOUT} scram b -k -j ${NCPU}  runtests "
  echo $UTESTS_CMD > $WORKSPACE/unitTests.log
  (eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/unitTests.log 2>&1 || true
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
    echo 'DQM_TESTS;OK,DQM Unit Tests,See Logs,DQMTestsResults' >> ${RESULTS_FILE}/unittest.txt
  fi

  TEST_ERRORS=$(grep -i 'had errors\|recipe for target' $WORKSPACE/unitTests.log | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
  TEST_ERRORS=`grep -i "had errors" $WORKSPACE/unitTests.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/unitTests.log` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the unit tests"
    echo 'UNIT_TEST_RESULTS;ERROR,Unit Tests,See Log,unitTests.log' >> ${RESULTS_FILE}/unittest.txt
    ALL_OK=false
    UNIT_TESTS_OK=false
    mark_commit_status_all_prs 'unittest' 'error' -u "${BUILD_URL}" -d "Some unit tests were failed." || true
  else
    mark_commit_status_all_prs 'unittest' 'success' -u "${BUILD_URL}" -d "Passed" || true
    echo 'UNIT_TEST_RESULTS;OK,Unit Tests,See Log,unitTests.log' >> ${RESULTS_FILE}/unittest.txt
  fi
else
  echo 'UNIT_TEST_RESULTS;NOTRUN' >> ${RESULTS_FILE}/unittest.txt
fi

#
# Matrix tests
#

if [ "X$TEST_CONTEXT" = "X" ] ; then
  MATRIX_EXTRAS=$(echo $(grep 'PR_TEST_MATRIX_EXTRAS=' $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||'),${MATRIX_EXTRAS} | tr ' ' ','| tr ',' '\n' | grep '^[0-9]' | sort | uniq | tr '\n' ',' | sed 's|,*$||')
else
  MATRIX_EXTRAS=$(echo $(grep "PR_TEST_MATRIX_EXTRAS_${TEST_CONTEXT}=" $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||'),${MATRIX_EXTRAS} | tr ' ' ','| tr ',' '\n' | grep '^[0-9]' | sort | uniq | tr '\n' ',' | sed 's|,*$||')
fi
if [ ! "X$MATRIX_EXTRAS" = X ]; then
  MATRIX_EXTRAS="-l $MATRIX_EXTRAS"
fi

if [ "X$DO_SHORT_MATRIX" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$ONLY_FIREWORKS" = false -a "$RUN_TESTS" = "true" ]; then
  mark_commit_status_all_prs 'relvals' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running RelVals" ${NO_POST}
  echo '--------------------------------------'
  mkdir "$WORKSPACE/runTheMatrix-results"
  pushd "$WORKSPACE/runTheMatrix-results"
    case $TEST_CONTEXT-$CMSSW_IB in
      -*SLHCDEV*)
        SLHC_PARAM='-w upgrade'
        WF_LIST="-l 10000,10061,10200,10261,10800,10861,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
        ;;
      -*SLHC*)
        SLHC_PARAM='-w upgrade'
        WF_LIST="-l 10000,10061,10200,10261,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
        ;;
      -*)
        WF_LIST="-s $MATRIX_EXTRAS"
        ;;
      GPU-*)
        WF_LIST="$MATRIX_EXTRAS"
        ;;
    esac

    # MATRIX_TIMEOUT is set by jenkins
    dateBefore=$(date +"%s")
    [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && EXTRA_MATRIX_ARGS="--job-reports $EXTRA_MATRIX_ARGS"
    if [ -f ${CMSSW_RELEASE_BASE}/src/Validation/Performance/python/TimeMemoryJobReport.py ]; then
        [ $(runTheMatrix.py --help | grep 'command' | wc -l) -gt 0 ] && EXTRA_MATRIX_ARGS="--command '--customise Validation/Performance/TimeMemoryJobReport.customiseWithTimeMemoryJobReport' $EXTRA_MATRIX_ARGS"
    fi
    RELVALS_CMD="timeout $MATRIX_TIMEOUT runTheMatrix.py $EXTRA_MATRIX_ARGS $SLHC_PARAM -j $(${COMMON}/get_cpu_number.sh -2) $WF_LIST"
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
    echo 'MATRIX_TESTS;ERROR,Matrix Tests Outputs,See Logs,runTheMatrix-results' >> ${RESULTS_FILE}/relval.txt
    ALL_OK=false
    RELVALS_OK=false
    mark_commit_status_all_prs 'relvals' 'error' -u "${BUILD_URL}" -d "Errors found while running runTheMatrix" || true
  else
    mark_commit_status_all_prs 'relvals' 'success' -u "${BUILD_URL}" -d "Passed" || true
    echo "no errors in the RelVals!!"
    echo 'MATRIX_TESTS;OK,Matrix Tests Outputs,See Logs,runTheMatrix-results' >> ${RESULTS_FILE}/relval.txt

    if $DO_COMPARISON ; then
      echo 'COMPARISON;QUEUED,Comparison with the baseline,See results,See results' >> ${RESULTS_FILE}/comparison.txt
      TRIGGER_COMPARISON_FILE=$WORKSPACE/'comparison.properties'
      echo "Creating properties file $TRIGGER_COMPARISON_FILE"
      echo "RELEASE_FORMAT=$COMPARISON_REL" > $TRIGGER_COMPARISON_FILE
      echo "ARCHITECTURE=${ARCHITECTURE}" >> $TRIGGER_COMPARISON_FILE
      echo "PULL_REQUEST_NUMBER=$REPORT_H_CODE" >> $TRIGGER_COMPARISON_FILE
      echo "PULL_REQUESTS=${PULL_REQUESTS}" >> $TRIGGER_COMPARISON_FILE
      echo "PULL_REQUEST_JOB_ID=${BUILD_NUMBER}" >> $TRIGGER_COMPARISON_FILE
      echo "REAL_ARCH=$REAL_ARCH" >> $TRIGGER_COMPARISON_FILE
      echo "WORKFLOWS_LIST=${WORKFLOW_TO_COMPARE}" >> $TRIGGER_COMPARISON_FILE
      echo "COMPARISON_ARCH=$COMPARISON_ARCH" >> $TRIGGER_COMPARISON_FILE
      echo "CMSDIST_ONLY=$CMSDIST_ONLY" >> $TRIGGER_COMPARISON_FILE
      echo "DOCKER_IMG=$DOCKER_IMG" >> $TRIGGER_COMPARISON_FILE
      mark_commit_status_all_prs 'comparison' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start" || true
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
fi

#
# AddOn Tetss
#
if [ "X$DO_ADDON_TESTS" = Xtrue -a "X$BUILD_OK" = Xtrue -a "$RUN_TESTS" = "true" ]; then
  mark_commit_status_all_prs 'addon' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running AddOn Tests" ${NO_POST}
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
  ADDON_CMD="CMSSW_SEARCH_PATH=$EX_DATA_SEARCH timeout 7200 addOnTests.py -j ${NCPU}"
  echo $ADDON_CMD > $WORKSPACE/addOnTests.log
  STIME=$(date +%s)
  (eval $ADDON_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/addOnTests.log
  set DTIME=$(date +%s)-$STIME
  echo 'END OF ADDON TESTS'
  echo '--------------------------------------'
  if [ -d addOnTests ] ; then
    mv addOnTests $WORKSPACE/addOnTests
  fi
  if [ $(grep ' tests passed, ' $WORKSPACE/addOnTests.log | wc -l) -eq 0 ] ; then
    echo "AddOnTest might have timed out: FAILED - $DTIME secs" >>  $WORKSPACE/addOnTests.log
  fi

  TEST_ERRORS=`grep -i -E ": FAILED .*" $WORKSPACE/addOnTests.log` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/addOnTests.log` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the addOnTests"
    echo 'ADDON_TESTS;ERROR,AddOn Tests,See Logs,addOnTests' >> ${RESULTS_FILE}/adddon.txt
    ALL_OK=false
    ADDON_OK=false
    mark_commit_status_all_prs 'addon' 'error' -u "${BUILD_URL}" -d "Errors in the addOnTests" || true
  else
    mark_commit_status_all_prs 'addon' 'success' -u "${BUILD_URL}" -d "Passed" || true
    echo "no errors in the addOnTests!!"
    echo 'ADDON_TESTS;OK,AddOn Tests,See Logs,addOnTests' >> ${RESULTS_FILE}/adddon.txt
  fi
fi

MB_TESTS_OK=NOTRUN
if [ $DO_MB_COMPARISON=false -a "X$BUILD_OK" = "Xtrue" -a "$RUN_TESTS" = "true" ] ; then
  if has_jenkins_artifacts material-budget/${CMSSW_VERSION}/${SCRAM_ARCH}/Images ; then
    mark_commit_status_all_prs 'material-budget' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
    mkdir $LOCALRT/material-budget
    MB_TESTS_OK=OK
    pushd $LOCALRT/material-budget
      $CMS_BOT_DIR/run-material-budget > $WORKSPACE/material-budget.log 2>&1 || MB_TESTS_OK=ERROR
      if [ "$MB_TESTS_OK" = "OK" ] ; then
        $CMS_BOT_DIR/compare-material-budget $LOCALRT/material-budget || MB_TESTS_OK=ERROR
      fi
    popd
    mv $LOCALRT/material-budget $WORKSPACE/material-budget
    mark_commit_status_all_prs 'material-budget' 'success' -u "${BUILD_URL}" -d "Passed" || true
    echo "MATERIAL_BUDGET;${MB_TESTS_OK},Material budge,See Logs,material-budget" >> ${RESULTS_FILE}/mbudget.txt
    if [ "$MB_TESTS_OK" = "ERROR" ] ; then
      MB_TESTS_OK=false
    else
      MB_TESTS_OK=true
    fi
  fi
fi

#
# Valgrind tests
#
for WF in ${WORKFLOWS_FOR_VALGRIND_TEST//,/ }; do
  mark_commit_status_all_prs 'valgrind' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Valgrind" ${NO_POST}

  echo 'I will run valgrind for the following workflow'
  echo $WF;
  mkdir -p "$WORKSPACE/valgrindResults-"$WF
  pushd "$WORKSPACE/valgrindResults-"$WF
  runTheMatrix.py --command '-n 10 --prefix "time valgrind --tool=memcheck --suppressions=$CMSSW_RELEASE_BASE/src/Utilities/ReleaseScripts/data/cms-valgrind-memcheck.supp --num-callers=20 --xml=yes --xml-file=valgrind.xml " ' -l $WF
  mark_commit_status_all_prs 'valgrind' 'success' -u "${BUILD_URL}" -d "Passed" || true
  popd
done


#
# Enabled bot tests
#
for BT in ${ENABLE_BOT_TESTS}; do
    if [ "$BT" = "PROFILING" ]; then
        PROFILING_WORKFLOWS=$(echo $(grep "PR_TEST_MATRIX_EXTRAS_PROFILING=" $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||'), | tr ' ' ','| tr ',' '\n' | grep '^[0-9]' | sort | uniq | tr '\n' ',' | sed 's|,*$||')
         pushd $WORKSPACE
         git clone --depth 1 https://github.com/cms-cmpwg/profiling.git
         popd
         mark_commit_status_all_prs 'profiling' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
         report_pull_request_results_all_prs_with_commit "TESTS_RUNNING" --report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --add-message "Running Profling" ${NO_POST}
         mkdir -p $WORKSPACE/upload/profiling/
         echo "<html><head></head><title>Profiling results</title><body><ul>" > $WORKSPACE/upload/profiling/index.html
         for PROFILING_WORKFLOW in $PROFILING_WORKFLOWS;do
             $WORKSPACE/profiling/Gen_tool/Gen.sh $CMSSW_IB || true
             $WORKSPACE/profiling/Gen_tool/runall.sh $CMSSW_IB || true
             $WORKSPACE/profiling/Gen_tool/runall_cpu.sh $CMSSW_IB || true
             pushd $WORKSPACE/$CMSSW_IB/src/$PROFILING_WORKFLOW
             ./profile.sh $CMSSW_IB || true
             echo "<li><a href=\"$PROFILING_WORKFLOW/\">$PROFILING_WORKFLOW/</a> </li>" >> $WORKSPACE/upload/profiling/index.html
             get_jenkins_artifacts igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling/${PROFILING_WORKFLOW}/RES_CPU_step3.txt  ${CMSSW_IB}_RES_CPU_step3.txt || true
             $WORKSPACE/profiling/Analyze_tool/compare_cpu_txt.py --old ${CMSSW_IB}_RES_CPU_step3.txt --new RES_CPU_step3.txt > RES_CPU_compare_$PROFILING_WORKFLOW.txt || true
             mkdir -p $WORKSPACE/upload/profiling/
             cp -p RES_CPU_compare_$PROFILING_WORKFLOW.txt $WORKSPACE/upload/profiling/$d/ || true
             echo "<li><a href=\"$PROFILING_WORKFLOW/RES_CPU_compare_$PROFILING_WORKFLOW.txt\">Igprof Comparison cpu usage RECO produce methods.</a> </li>" >> $WORKSPACE/upload/profiling/index.html
             popd
             pushd $WORKSPACE/$CMSSW_IB/src || true
             for f in $(find $PROFILING_WORKFLOW -type f -name '*.sql3') ; do
               d=$(dirname $f)
               mkdir -p $WORKSPACE/upload/profiling/$d || true
               cp -p $f $WORKSPACE/upload/profiling/$d/ || true
               mkdir -p $LOCALRT/igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER} || true
               BASENAME=$(basename $f)
			ln -s /data/sdt/SDT/jenkins-artifacts/pull-request-integration/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/profiling/$d/$BASENAME $LOCALRT/igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/$BASENAME || true
               ls -l $WORKSPACE/igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/$BASENAME || true
               echo "<li><a href=\"https://cmssdt.cern.ch/SDT/cgi-bin/igprof-navigator/${CMSSW_IB}/${ARCHITECTURE}/profiling/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/${BASENAME//.sql3/}\"> $(basename $f)</a> </li>" >> $WORKSPACE/upload/profiling/index.html
             done
             for f in $(find $PROFILING_WORKFLOW -type f -name '*.json' ) ; do
               d=$(dirname $f)
               mkdir -p $WORKSPACE/upload/profiling/$d || true
               cp -p $f $WORKSPACE/upload/profiling/$d/ || true
               mkdir -p $WORKSPACE/upload/profiles/$d || true
               BASENAME=$(basename $f)
               mkdir -p $LOCALRT/profiling/${CMSSW_IB}/${ARCHITECTURE}/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER} || true
               ln -s /data/sdt/SDT/jenkins-artifacts/pull-request-integration/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/profiling/$d/$BASENAME $LOCALRT/profiling/${CMSSW_IB}/${ARCHITECTURE}/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/$BASENAME || true
               ls -l $LOCALRT/profiling/${CMSSW_IB}/${ARCHITECTURE}/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/$BASENAME || true
               AMP="&"
               echo "<li><a href=\"https://cmssdt.cern.ch/circles/web/piechart.php?local=false${AMP}dataset=${CMSSW_IB}/${ARCHITECTURE}/${PROFILING_WORKFLOW}/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index.html
             done
             echo "</ul></body></html>" >> $WORKSPACE/upload/profiling/index.html
             for f in $(find $PROFILING_WORKFLOW -type f -name '*.log' -o -name '*.txt') ; do
               d=$(dirname $f)
               mkdir -p $WORKSPACE/upload/profiling/$d || true
               cp -p $f $WORKSPACE/upload/profiling/$d/ || true
             done
             popd
         done
         mark_commit_status_all_prs 'profiling' 'success' -u "${BUILD_URL}" -d "Passed" || true
         echo 'CMSSW_PROFILING;OK,Profiling Results,See Logs,profiling' >> ${RESULTS_FILE}/profiling.txt
   fi
done


#evaluate results
TESTS_FAILED="Failed tests:"
if [ "X$BUILD_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  Build"
fi
if [ "X$CHK_HEADER_OK" = Xfalse ] ; then
  TESTS_FAILED="$TESTS_FAILED  HeaderConsistency"
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
if [ "X$PYTHON3_BUILD_OK" = Xfalse ]; then
  TESTS_FAILED="$TESTS_FAILED  Python3"
fi

prepare_upload_results

rm -f ${WORKSPACE}/report.txt
env | grep 'CMSSW_'
REPORT_OPTS="--report-pr ${REPORT_H_CODE} --pr-job-id ${BUILD_NUMBER} --recent-merges $RECENT_COMMITS_FILE $NO_POST"

if ${ALL_OK} ; then  # if non of the test failed (non of them set ALL_OK to false)
    if [ "${BUILD_LOG_RES}" = "ERROR" ] ; then
        BUILD_LOG_RES=" --add-comment 'Compilation Warnings: Yes'"
    else
        BUILD_LOG_RES=""
    fi
    REPORT_OPTS="TESTS_OK_PR ${REPORT_OPTS} ${BUILD_LOG_RES}"
    mark_commit_status_all_prs '' 'success' -u "${BUILD_URL}" -d "Passed" || true
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
    if [ "X$PYTHON3_BUILD_OK" = Xfalse ]; then
        $CMS_BOT_DIR/report-pull-request-results PYTHON3_FAIL        -f $WORKSPACE/upload/python3.log ${REPORT_GEN_OPTS}
    fi
    REPORT_OPTS="REPORT_ERRORS ${REPORT_OPTS}" # Doc:
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Failed: ${TESTS_FAILED}" || true
fi

rm -f all_done  # delete file
if [ -z ${NO_POST} ] ; then
    send_jenkins_artifacts $WORKSPACE/upload pull-request-integration/PR-${REPORT_H_CODE}/${BUILD_NUMBER} && touch all_done
    if [ -d $LOCALRT/das_query ] ; then
      send_jenkins_artifacts $LOCALRT/das_query das_query/PR-${REPORT_H_CODE}/${BUILD_NUMBER}/PR || true
    fi
    if [ -d $LOCALRT/profiling ]; then
        send_jenkins_artifacts $LOCALRT/profiling/${CMSSW_IB}/${ARCHITECTURE} profiling/${CMSSW_IB}/${ARCHITECTURE}/
    fi
    if [ -d $LOCALRT/igprof ]; then
        send_jenkins_artifacts $LOCALRT/igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling igprof/${CMSSW_IB}/${ARCHITECTURE}/profiling/
    fi
fi

if [ -f all_done ] ; then
  rm -f all_done
    # Doc: report everything back unless no matter if ALL_OK was true or false.
    report_pull_request_results_all_prs_with_commit ${REPORT_OPTS}
elif [ ! -z ${NO_POST} ] ; then
    # Doc: if --no-post flag is set, output comments and continue to next code block.
    report_pull_request_results_all_prs_with_commit ${REPORT_OPTS}
else
  echo "Error: upload to Jenkins server failed."
  exit 1
fi

COMP_MSG="Comparison job queued."
if [ $(grep 'COMPARISON;NOTRUN' $WORKSPACE/upload/testsResults/comparison.txt | wc -l) -gt 0 ] ; then
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
