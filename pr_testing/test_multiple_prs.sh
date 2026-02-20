#!/bin/bash -ex
# This script will be called by Jenkins job 'ib-run-pr-tests'
# and
# 1) will merge multiple PRs for multiple repos
# 2) run tests and post result on github
# ---
#common function
function order_workflow_list(){
  echo ${1} | tr ' ' '\n' | tr ',' '\n' | grep '^[a-z0-9]\|^all$' | sort -n | uniq | tr '\n' ',' | sed 's|,*$||'
}

function get_pr_baseline_worklflow() {
  order_workflow_list $($CMS_BOT_DIR/cmssw-pr-test-config $1),${2}
}

function get_compilation_warnings() {
  grep -E ': warning:|: warning #[0-9]+-D:' $1 | grep -E "/$CMSSW_IB/src/|^\s*src/" | sed -E "s|: warning #[0-9]+-D:|: warning:|;s|.*/$CMSSW_IB/||"
}

function get_warnings_files(){
  local logFile="$1"
  local changedFiles="$2"
  for i in $(cat $logFile | sed 's|^src/||;s|:.*||;s| ||g;s|[(].*||' | sort -u) ; do
    [ $(grep "$i" "$changedFiles" | wc -l) -gt 0 ] && echo $i
  done
}

function get_pr_relval_args() {
  local WF_ARGS
  local WF_LIST
  local WF_LIST2
  wf_args="$(eval echo \${EXTRA_MATRIX_ARGS$2})"
  if $1 || [ "${wf_args}" != "" ] ; then
     WF_LIST=$(get_pr_baseline_worklflow "$2")
     [ "$WF_LIST" = "" ] || WF_LIST="-l $WF_LIST"
     WF_LIST2=$(order_workflow_list "$(eval echo \${MATRIX_EXTRAS$2})")
     if [ "${WF_LIST2}" = "" ] ; then
       WF_ARGS="${WF_LIST}"
     else
       WF_ARGS="${WF_LIST};-l ${WF_LIST2} ${wf_args}"
     fi
  else
    WF_LIST=$(get_pr_baseline_worklflow "$2" "$(eval echo \${MATRIX_EXTRAS$2})")
    [ "$WF_LIST" = "" ] || WF_LIST="-l $WF_LIST"
    WF_ARGS="${WF_LIST} ${wf_args}"
  fi
  echo "${WF_ARGS}"
}

# Function to extract filenames by headername and append to indirectly-changed-files.txt
function extract_filenames() {
  local headername="$1"
  local input_file="./etc/dependencies/usedby.out"
  local output_file="$2"

  # Extract lines starting with headername, split them, and append each filename to the temp file
  grep "^$headername" "$input_file" | while read -r line; do
    # Split the line into an array
    IFS=' ' read -r -a array <<< "$line"

    # Loop through each element after the first (which is the headername)
    for filename in "${array[@]:1}"; do
      echo "$filename" >> "$output_file"
    done
  done
}

# Function to get indirectly changed files
function process_changed_files() {
  local directlyChangedFiles="$1"
  local allChangedFiles="$2"
  cat </dev/null >"$WORKSPACE/indirectly-changed-files.txt"
  # Iterate over each line in $WORKSPACE/changed-files.txt
  while IFS= read -r headername; do
    # Call the function to extract files that use $headername and append them to $WORKSPACE/indirectly-changed-files
    extract_filenames "$headername" "$WORKSPACE/indirectly-changed-files.txt"
  done < "$directlyChangedFiles"
  # Merge lists
  sort -u "$directlyChangedFiles" $WORKSPACE/indirectly-changed-files.txt > "$allChangedFiles"
}

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path

# Constants
echo LD_LIBRARY_PATH=${LD_LIBRARY_PATH} || true
ls ${LD_LIBRARY_PATH} || true
export SCRAM_PREFIX_PATH=${CMS_BOT_DIR}/das-utils
source ${CMS_BOT_DIR}/cmsrep.sh
CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
CONFIG_MAP=$CMS_BOT_DIR/config.map
[ "${USE_IB_TAG}" != "true" ] && export USE_IB_TAG=false
readarray -t REQUIRED_GPU_TYPES < <(tr -d '\r' < "${CMS_BOT_DIR}/gpu_flavors.txt")
readarray -t ONDEMAND_GPU_TYPES < <(tr -d '\r' < "${CMS_BOT_DIR}/gpu_flavors_ondemand.txt")
ALL_GPU_TYPES=( ${REQUIRED_GPU_TYPES[@]} ${ONDEMAND_GPU_TYPES[@]} )

[ "${EXTRA_RELVALS_TESTS}" = "" ] && EXTRA_RELVALS_TESTS="THREADING HIGH_STATS NANO $(echo ${ALL_GPU_TYPES[@]} | tr '[a-z]' '[A-Z]')"
EXTRA_RELVALS_TESTS=$(echo ${EXTRA_RELVALS_TESTS} | tr ' ' '\n' | grep -v THREADING | grep -v RNTUPLE | grep -v GPU | tr '\n' ' ')
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
if [ -z ${ARCHITECTURE} ] ; then
    ARCHITECTURE=$(echo ${CONFIG_LINE} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )
fi
export SCRAM_ARCH=${ARCHITECTURE}
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
export JENKINS_PREFIX
RESULTS_FILE=${RESULTS_DIR}.txt
PR_NUMBER=$(echo ${PULL_REQUEST} | sed 's|.*#||')
PR_REPO=$(echo ${PULL_REQUEST} | sed 's|#.*||')
PR_NUM=$(echo ${PULL_REQUEST} | md5sum | sed 's| .*||' | cut -c27-33)
UPLOAD_UNIQ_ID=PR-${PR_NUM}/${BUILD_NUMBER}
PR_RESULT_URL="https://cmssdt.cern.ch/SDT/${JENKINS_PREFIX}-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}"
PR_COMMENT_TEXT_URL="https://cmssdt.cern.ch/SDT/cgi-bin/get_pr_results/${JENKINS_PREFIX}-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}/pr-result"
NCPU=$(${COMMON}/get_cpu_number.sh)
if [[  $NODE_NAME == *"cms-cmpwg-0"* ]]; then
   let NCPU=${NCPU}/2
fi
let NCPU2=${NCPU}*2
rm -rf ${RESULTS_DIR} ${RESULTS_FILE}
mkdir ${RESULTS_DIR}

TEST_RELVALS_INPUT=false
DO_COMPARISON=false
DO_MB_COMPARISON=false
DO_DAS_QUERY=false
DO_CRAB_TESTS=false
DO_HLT_P2_TIMING=false
DO_HLT_P2_INTEGRATION=false
ENABLE_MEMORY_PROFILE=false
[ "${UPLOAD_TO_PACKAGE_STORE}" != "" ] || UPLOAD_TO_PACKAGE_STORE=true
[ $(echo ${ARCHITECTURE}   | grep "_amd64_" | wc -l) -gt 0 ] && DO_COMPARISON=true
[ $(echo ${RELEASE_FORMAT} | grep 'SAN_X'   | wc -l) -gt 0 ] && DO_COMPARISON=false
BUILD_VERBOSE=true
if [ "${BUILD_VERBOSE}" = "true" ] ; then
  BUILD_VERBOSE="-v"
else
  BUILD_VERBOSE=""
fi

PRODUCTION_RELEASE=false
CMSSW_BRANCH=$(echo "${CONFIG_LINE}" | sed 's|.*RELEASE_BRANCH=||;s|;.*||')
CMSSW_DEVEL_BRANCH=$(cd $CMS_BOT_DIR; ${CMSBOT_PYTHON_CMD} -c 'from releases import CMSSW_DEVEL_BRANCH; print(CMSSW_DEVEL_BRANCH)')
CMSSW_DEVEL_REL=false
CMSSW_DEVEL_PROD_ARCH=false
if [ "${CMSSW_BRANCH}" = "master" ] ; then
  CMSSW_BRANCH=${CMSSW_DEVEL_BRANCH}
  CMSSW_DEVEL_REL=true
fi
if [ "${CMSBOT_SET_ENV_ENABLE_MEMORY_PROFILE}" = "true" ] ; then ENABLE_MEMORY_PROFILE=true ; fi
if [ $(echo "${CONFIG_LINE}" | grep "PROD_ARCH=1" | wc -l) -gt 0 ] ; then
  if [ $(echo "${CONFIG_LINE}" | grep "ADDITIONAL_TESTS=" | wc -l) -gt 0 ] ; then
    PRODUCTION_RELEASE=true
    ENABLE_MEMORY_PROFILE=true
    if ${CMSSW_DEVEL_REL} ; then
      DO_DAS_QUERY=true
      TEST_RELVALS_INPUT=true
      CMSSW_DEVEL_PROD_ARCH=true
    fi
  fi
fi

IFS=',' read -ra SELECTED_GPU_TYPES <<< "$SELECTED_GPU_TYPES"

for gpu_type in ${SELECTED_GPU_TYPES[@]} ; do
  VAR_NAME="MATRIX_EXTRAS_${gpu_type}"
  if [ -z "${!VAR_NAME}" ]; then
    eval "$VAR_NAME=\"${MATRIX_EXTRAS_GPU}\""
  fi
  VAR_NAME="EXTRA_MATRIX_ARGS_${gpu_type}"
  if [ -z "${!VAR_NAME}" ]; then
    eval "$VAR_NAME=\"${EXTRA_MATRIX_ARGS_GPU}\""
  fi
done

if [ "${BUILD_ONLY}" = "true" ] ; then
  DO_COMPARISON=false
fi
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

DISABLE_CMS_DEPRECATED=false
DISABLE_GPU_TESTS=true
if [ $(uname -m) != "aarch64" ] ; then
  DISABLE_GPU_TESTS=false
fi
CMSSW_QUEUE=$(echo ${RELEASE_FORMAT} | sed 's/_X.*/_X/')  # RELEASE_FORMAT - CMSSW_10_4_X_2018-11-26-2300
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | tr ',' ' ' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//' )  # to make consistent separation in list
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )  # Repos without pull number
UNIQ_REPO_NAMES=$(echo ${UNIQ_REPOS} | tr ' ' '\n' | sed 's|.*/||' )
UNIQ_REPO_NAMES_WITH_COUNT=$(echo ${UNIQ_REPO_NAMES} | sort | uniq -c )
RPM_UPLOAD_REPO=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep -v '/cmssw#' | grep -v '/cms-bot#' | sort | uniq | md5sum | sed 's| .*||')
if [ $(echo $CMSSW_QUEUE | cut -d_ -f2) -lt 13 ] ; then
  export DISABLE_CMS_DEPRECATED=true
  export DISABLE_GPU_TESTS=true
fi

let WEEK_NUM=$(tail -1 $CMS_BOT_DIR/ib-weeks | sed 's|.*-||;s|^0*||')%2 || true
CMS_WEEKLY_REPO=cms.week${WEEK_NUM}

# this is to automount directories in cvmfs, otherwise they wont show up
ls /cvmfs/cms.cern.ch
ls /cvmfs/cms-ib.cern.ch || true

which scram 2>/dev/null || source /cvmfs/cms.cern.ch/cmsset_default.sh

# Put hashcodes of last commits to a file. Mostly used for commenting back
COMMIT=$(${CMSBOT_PYTHON_CMD} ${CMS_BOT_DIR}/process-pull-request.py -c -r ${PR_REPO} ${PR_NUMBER})
echo "${PULL_REQUEST}=${COMMIT}" > ${WORKSPACE}/prs_commits
cp ${WORKSPACE}/prs_commits ${WORKSPACE}/prs_commits.txt

mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d 'Setting up build environment' --reset
PR_COMMIT_STATUS="optional"
if [ "${BUILD_ONLY}" = "true" ] ; then
  PR_COMMIT_STATUS="build_only"
  export REQUIRED_TEST=false
elif $REQUIRED_TEST ; then
  PR_COMMIT_STATUS="required"
fi
mark_commit_status_all_prs "${PR_COMMIT_STATUS}" 'success' -d 'OK' -u "${BUILD_URL}"

echo -n "**Summary**: ${PR_RESULT_URL}/summary.html" > ${RESULTS_DIR}/09-report.res
CMSSW_VERSION=${RELEASE_FORMAT} $CMS_BOT_DIR/report-pull-request-results GET_BASE_MESSAGE --report-url ${PR_RESULT_URL} \
    --commit ${COMMIT} --report-file ${RESULTS_DIR}/09-report.res ${REPORT_OPTS}
echo "**User test area**: For local testing, you can use \`/cvmfs/cms-ci.cern.ch/week${WEEK_NUM}/${PR_REPO}/${PR_NUMBER}/${BUILD_NUMBER}/install.sh\` to create a dev area with all the needed externals and cmssw changes." >> ${RESULTS_DIR}/09-report.res
echo "" >> ${RESULTS_DIR}/09-report.res

echo_section "Pull request checks"
# Check if same organization/repo PRs
if [ $(echo ${UNIQ_REPO_NAMES_WITH_COUNT}  | grep -v '1 ' | wc -w ) -gt 0 ]; then
    echo "ERROR: multiple PRs from different organisations but same repos:    ${UNIQ_REPO_NAMES_WITH_COUNT}" > ${RESULTS_DIR}/10-report.res
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Multiple PRs from different repositories"
    exit 0
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
        echo "ERROR: PRs for repo ${U_REPO} wants to merge to different branches: ${UNIQ_MASTERS}" > ${RESULTS_DIR}/10-report.res
        prepare_upload_results
        mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Invalid branch merge."
        exit 0
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
if [ "${CONFIG_LINE}" == "" ] ; then exit 1 ; fi

export CMSDIST_TAG=$(echo ${CONFIG_LINE} | sed 's/^.*CMSDIST_TAG=//' | sed 's/;.*//')

COMP_QUEUE=
case $CMSSW_QUEUE in
  CMSSW_9_4_MAOD_X*|CMSSW_9_4_AN_X* ) COMP_QUEUE=$CMSSW_QUEUE ;;
  * ) COMP_QUEUE=$(echo $CMSSW_QUEUE | cut -d_ -f1-3)_X;;
esac
if [ "X$DEV_BRANCH" = "X$COMP_QUEUE" ] ; then IS_DEV_BRANCH=true ; fi

CMSSW_IB="$RELEASE_FORMAT"  # We are getting CMSSW_IB, so that we wont rebuild all the software
[ "$COMPARISON_ARCH" = "" ] && COMPARISON_ARCH=$(cat $CONFIG_MAP | grep "RELEASE_QUEUE=$COMP_QUEUE;" | grep -v "DISABLED=1" | grep 'PROD_ARCH=1' | sed 's|^.*SCRAM_ARCH=||;s|;.*$||')
if [[ $RELEASE_FORMAT != *-* ]]; then
  grep '^CMSSW_' $CMS_BOT_DIR/ignore-releases-for-tests > $WORKSPACE/release-with-errors || true
  echo "CMSSW_ERROR" >> $WORKSPACE/release-with-errors
  if [ $(echo ${RELEASE_FORMAT} | grep _X | wc -l) -gt 0 ] ; then
    CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $RELEASE_FORMAT | grep '^CMSSW ' | grep -v -f "$WORKSPACE/release-with-errors" | awk '{print $2}' | sort -r | head -1)
  fi
  if [ "$CMSSW_IB" = "" ] ; then
    CMSSW_IB=$(scram -a $SCRAM_ARCH l -c $CMSSW_QUEUE  | grep '^CMSSW ' | grep -v -f "$WORKSPACE/release-with-errors" | awk '{print $2}' | sort -r | head -1)
    if [ "$CMSSW_IB" = "" ] ; then
      echo "I was not able to find a release to test this PR. See the Jenkins logs for more details" > ${RESULTS_DIR}/10-report.res
      prepare_upload_results
      mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Unable to find CMSSW release for ${CMSSW_QUEUE}/${SCRAM_ARCH}"
      exit 0
    fi
  fi
  rm -f $WORKSPACE/release-with-errors
fi
if [ "$COMPARISON_REL" = "" ] ; then
  if [ "$(echo $CMSSW_IB | sed 's|_X_.*|_X|')" = "$COMP_QUEUE" ] ; then
    COMPARISON_REL=$CMSSW_IB
  else
    COMPARISON_REL=$(echo $CMSSW_IB | sed 's|_[A-Z][A-Z0-9]*_X_|_X_|')
  fi
fi
[ "${RELEASE_FORMAT}" != "${CMSSW_IB}" ] && sed -i -e "s|${RELEASE_FORMAT}|${CMSSW_IB}|" ${RESULTS_DIR}/09-report.res

if [ "${USE_BASELINE}" = "self" ] ; then
  COMPARISON_REL="$CMSSW_IB"
  COMPARISON_ARCH="$SCRAM_ARCH"
fi

WORKFLOWS_PR_LABELS=""
scram -a $SCRAM_ARCH project $CMSSW_IB
if $DO_COMPARISON ; then
  mkdir $WORKSPACE/ib-baseline-tests
  pushd $WORKSPACE/ib-baseline-tests
    COMP_OS=$(echo $COMPARISON_ARCH | sed 's|_.*||')
    if [ "${COMP_OS}" = "slc7" ] ; then COMP_OS="cc7"; fi
    echo "RELEASE_FORMAT=$COMPARISON_REL" > run-baseline-${BUILD_ID}-01.default
    echo "ARCHITECTURE=$COMPARISON_ARCH" >> run-baseline-${BUILD_ID}-01.default
    echo "DOCKER_IMG=cmssw/${COMP_OS}"   >> run-baseline-${BUILD_ID}-01.default
    echo "TEST_FLAVOR="                  >> run-baseline-${BUILD_ID}-01.default
    echo "REAL_ARCH=${RELVAL_REAL_ARCH}" >> run-baseline-${BUILD_ID}-01.default
    echo "PRODUCTION_RELEASE=true"       >> run-baseline-${BUILD_ID}-01.default
    echo "PULL_REQUESTS=${PULL_REQUESTS}" >> run-baseline-${BUILD_ID}-01.default
    WF_LIST=$(get_pr_baseline_worklflow)
    [ "${WF_LIST}" = "" ] || WF_LIST="-l ${WF_LIST}"
    echo "WORKFLOWS=-s ${WF_LIST}" >> run-baseline-${BUILD_ID}-01.default

    PR_LABELS=$(curl -s https://api.github.com/repos/${PR_REPO}/issues/${PR_NUMBER}/labels | grep '"name":' | sed 's|.*: *||;s|"||g;s|-pending||;s|-approved||;s|-rejected||' | tr ',\n' '  ' | tr '[a-z-]' '[A-Z_]')
    EX_WFS=""
    for l in ${PR_LABELS} ; do
       EX_WFS="${EX_WFS},$(get_pr_baseline_worklflow _LAB_${l})"
    done
    EX_WFS=$(echo "${EX_WFS}" | sed 's|^,*||;s|,*$||;s|,,*|,|g')
    if [ "${EX_WFS}" != "" ] ; then
      (
        set +x
        cd $WORKSPACE/$CMSSW_IB
        eval `scram run -sh`
        runTheMatrix.py -n -e | grep '\[1\]:' | sed 's| .*||' > wfs.all
        runTheMatrix.py -n -e -s ${WF_LIST} | grep '\[1\]:' | sed 's| .*||' > wfs.default
        set -x
      )
      for wf in $(echo ${EX_WFS} | tr ',' '\n') ; do
        if grep -q "^${wf}$" $WORKSPACE/$CMSSW_IB/wfs.all ; then
          if ! grep -q "^${wf}$" $WORKSPACE/$CMSSW_IB/wfs.default ; then
            WORKFLOWS_PR_LABELS="${WORKFLOWS_PR_LABELS},${wf}"
          else
            echo "WARNING: Workflow already part of default tests: $wf"
          fi
        else
          echo "WARNING: No such workflow: $wf"
        fi
      done
      WORKFLOWS_PR_LABELS=$(echo "${WORKFLOWS_PR_LABELS}" | sed 's|^,*||')
      echo "WORKFLOWS_PR_LABELS=${WORKFLOWS_PR_LABELS}"
      if [ "${WORKFLOWS_PR_LABELS}" != "" ] ; then
        grep -v '^\(WORKFLOWS\|MATRIX_ARGS\)=' run-baseline-${BUILD_ID}-01.default > run-baseline-${BUILD_ID}-03.default
        echo "WORKFLOWS=-l ${WORKFLOWS_PR_LABELS}" >> run-baseline-${BUILD_ID}-03.default
      fi
    fi
    if [ "${MATRIX_EXTRAS}" != "" ] ; then
      WF_LIST=$(order_workflow_list ${MATRIX_EXTRAS})
      grep -v '^\(WORKFLOWS\|MATRIX_ARGS\)=' run-baseline-${BUILD_ID}-01.default > run-baseline-${BUILD_ID}-02.default
      echo "WORKFLOWS=-l ${WF_LIST}"    >> run-baseline-${BUILD_ID}-02.default
      echo "MATRIX_ARGS=${EXTRA_MATRIX_ARGS}" >> run-baseline-${BUILD_ID}-02.default
    fi

    for ex_type in ${EXTRA_RELVALS_TESTS} ; do
      [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep "^${ex_type}$" | wc -l) -gt 0 ] || continue
      WF_LIST=$(get_pr_baseline_worklflow "_${ex_type}")
      [ "$WF_LIST" != "" ] || continue
      ex_type_lc=$(echo ${ex_type} | tr '[A-Z]' '[a-z]')
      grep -v '^\(WORKFLOWS\|MATRIX_ARGS\|TEST_FLAVOR\)=' run-baseline-${BUILD_ID}-01.default > run-baseline-${BUILD_ID}-01.${ex_type_lc}
      echo "WORKFLOWS=-l ${WF_LIST}"   >> run-baseline-${BUILD_ID}-01.${ex_type_lc}
      echo "TEST_FLAVOR=${ex_type_lc}" >> run-baseline-${BUILD_ID}-01.${ex_type_lc}
      WF_LIST=$(order_workflow_list $(eval echo "\${MATRIX_EXTRAS_${ex_type}}"))
      [ "${WF_LIST}" != "" ] || continue
      WF_ARGS=$(eval echo "\${EXTRA_MATRIX_ARGS_${ex_type}}")
      grep -v '^\(WORKFLOWS\|MATRIX_ARGS\)=' run-baseline-${BUILD_ID}-01.${ex_type_lc} > run-baseline-${BUILD_ID}-02.${ex_type_lc}
      echo "WORKFLOWS=-l ${WF_LIST}"   >> run-baseline-${BUILD_ID}-02.${ex_type_lc}
      echo "MATRIX_ARGS=${WF_ARGS}" >> run-baseline-${BUILD_ID}-02.${ex_type_lc}
    done
  popd
  send_jenkins_artifacts $WORKSPACE/ib-baseline-tests/ ib-baseline-tests/
  rm -rf $WORKSPACE/ib-baseline-tests
fi

#Incase week is changed but tests were run for last week
let IB_WEEK=$(scram -a $SCRAM_ARCH list -c ${CMSSW_IB} | sed "s|/${SCRAM_ARCH}/.*||;s|^.*\([0-9]\)$|\1|")%2 || true
if [ "${IB_WEEK}" != "${WEEK_NUM}" ] ; then
  sed -i -e "s|/week${WEEK_NUM}/|/week${IB_WEEK}/|" ${RESULTS_DIR}/09-report.res
  WEEK_NUM=${IB_WEEK}
  CMS_WEEKLY_REPO=cms.week${WEEK_NUM}
fi

PKG_TOOL_BRANCH=$(echo ${CONFIG_LINE} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )
PKG_TOOL_VERSION=$(echo ${PKG_TOOL_BRANCH} | cut -d- -f 2)
if [[ ${PKG_TOOL_VERSION} -lt 32 && ! -z $(echo ${UNIQ_REPO_NAMES} | tr ' ' '\n' | grep -v -w cmssw | grep -v -w cmsdist | grep -v -w cms-bot ) ]] ; then
    echo "ERROR: RELEASE_FORMAT ${CMSSW_QUEUE} uses PKG_TOOL_BRANCH ${PKG_TOOL_BRANCH} which is lower then required to test externals." > ${RESULTS_DIR}/10-report.res
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Invalid PKGTOOLS version to test external packages."
    exit 0
fi

# Do git pull --rebase for each PR except for /cmssw
for U_REPO in $(echo ${UNIQ_REPOS} | tr ' ' '\n'  | grep -v '/cmssw$' ); do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        ERR=false
        git_clone_and_merge "$(get_cached_GH_JSON "${PR}")" || ERR=true
	if [[ $(echo ${PR} | grep "cmsdist") ]]; then  # Check for CRAB updates to trigger unit test
	    pushd cmsdist
	    UPDATES=$(git diff origin/${BASE_BRANCH} --name-only)
            if [[ $(echo ${UPDATES} | grep -E 'crab-.*(spec|file)') ]]; then
                echo "There is a CRAB update."
		DO_CRAB_TESTS=true
            fi
	    popd
        fi
        if ${ERR} ; then
            echo "Failed to merge pull requests ${PR}." > ${RESULTS_DIR}/10-report.res
            prepare_upload_results
            mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Failed to merge ${PR}"
            exit 0
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
    PKG_ORG=$(echo ${PKG_REPO} | sed 's|/.*||')
    case "$PKG_NAME" in  # We do not care where the repo is kept (ex. cmssw organisation or other)
        cmssw)
            CMSSW_ORG="${PKG_ORG}"
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
                    echo "ERROR: There was an issue generating parameters for cmsBuild '--source' flag for spec file ${SPEC_NAME} from ${PKG_REPO} repo." > ${RESULTS_DIR}/10-report.res
                    prepare_upload_results
                    mark_commit_status_all_prs '' 'error' -u "${BUILD_URL}" -d "Error getting source flag for ${PKG_REPO}, fix spec ${SPEC_NAME}"
                    exit 0
                fi
            done
	      ;;
	  esac
done
if $CMSDIST_ONLY ; then
  DO_DAS_QUERY=false
  TEST_RELVALS_INPUT=false
fi

# Prepera html templates
cp $CMS_BOT_DIR/templates/PullRequestSummary.html $WORKSPACE/summary.html
sed -e "s|@JENKINS_PREFIX@|$JENKINS_PREFIX|g;" $CMS_BOT_DIR/templates/js/renderPRTests.js > $WORKSPACE/renderPRTests.js

mkdir -p ${RESULTS_DIR}
touch ${RESULTS_FILE} ${RESULTS_DIR}/comparison.txt
echo "PR_NUMBERS;$PULL_REQUESTS" >> ${RESULTS_FILE}
echo 'BASE_IB;'$CMSSW_IB >> ${RESULTS_FILE}
echo 'BUILD_NUMBER;'$BUILD_NUMBER >> ${RESULTS_FILE}
echo "PR_NUMBER;$PR_NUM" >> ${RESULTS_FILE}
echo "COMPARISON_IB;$COMPARISON_REL" >> ${RESULTS_FILE}

PR_EXTERNAL_REPO=""
TEST_DASGOCLIENT=false
SKIP_STATIC_CHECKS=false
[ $(echo ",${SKIP_TESTS}," | grep ',static,' | wc -l) -gt 0 ] && SKIP_STATIC_CHECKS=true
if ${BUILD_EXTERNAL} ; then
    export USE_IB_TAG=false
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
        REF_REPO="--reference "$(readlink /cvmfs/cms-ib.cern.ch/sw/$(uname -m)/$(echo $CMS_WEEKLY_REPO | sed 's|^cms.||'))
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
    CMSBUILD_ARGS="--builders 2  --tag ${PR_NUM}"
    BUILD_OPTS=$(echo $CONFIG_LINE     | tr ';' '\n' | grep "^BUILD_OPTS=" | sed 's|^BUILD_OPTS=||')
    MULTIARCH_OPTS=$(echo $CONFIG_LINE | tr ';' '\n' | grep "^MULTIARCH_OPTS=" | sed 's|^MULTIARCH_OPTS=||')

    if [ ${PKG_TOOL_VERSION} -gt 31 ] ; then
      CMSBUILD_ARGS="${CMSBUILD_ARGS} --define cmsswdata_version_link  --monitor --log-deps --force-tag --tag hash --delete-build-directory --link-parent-repository"
      if [ "${ALLOW_VERSION_SUFFIX}" = "true" ] ; then
        CMSBUILD_ARGS="${CMSBUILD_ARGS} --define allow_version_suffix"
      fi
      if [ $(echo "${CONFIG_LINE}" | grep "DEBUG_EXTERNALS=" | wc -l) -gt 0 ] ; then
        dbg_pkgs=$(echo "${CONFIG_LINE}" | tr ';' '\n' | grep "^DEBUG_EXTERNALS=" | sed 's|.*=||')
        CMSBUILD_ARGS="${CMSBUILD_ARGS} --define cms_debug_packages=${dbg_pkgs}"
      fi
      if [ $(echo "${BUILD_OPTS}" | tr ',' '\n' | grep '^estats$') = "estats" ] ; then
        if [ ${PKG_TOOL_VERSION} -ge 34 ] ; then
          if ${CMS_BOT_DIR}/get-external-avg-stats.py ${ARCHITECTURE} > ${WORKSPACE}/externals-resource-usage.json ; then
            CMSBUILD_ARGS="${CMSBUILD_ARGS} --estats ${WORKSPACE}/externals-resource-usage.json --builders ${NCPU}"
          fi
        fi
      fi
    fi
    if [ $(grep 'upload-package-store-s3' pkgtools/cmsBuild | wc -l) -gt 0 ] ; then
      [ "${CMSBOT_SET_ENV_NO_PACKAGE_STORE}" = "true" ] && UPLOAD_TO_PACKAGE_STORE=false
      if $UPLOAD_TO_PACKAGE_STORE ; then
        CMSBUILD_ARGS="${CMSBUILD_ARGS} --upload-package-store-s3"
      else
        CMSBUILD_ARGS="${CMSBUILD_ARGS} --no-package-store"
      fi
    fi

    PKGS="cms-common cms-git-tools cmssw-tool-conf"
    COMPILATION_CMD="PYTHONPATH= ./pkgtools/cmsBuild --server http://${CMSREP_IB_SERVER}/cgi-bin/cmspkg --upload-server ${CMSREP_IB_SERVER} \
        ${CMSBUILD_ARGS} -i $WORKSPACE/$BUILD_DIR $REF_REPO \
        $SOURCE_FLAG --arch $ARCHITECTURE -j ${NCPU} $(cmsbuild_args "${BUILD_OPTS}" "${MULTIARCH_OPTS}" "${ARCHITECTURE}")"
    PR_EXTERNAL_REPO="PR_$(echo ${RPM_UPLOAD_REPO}_${CMSSW_QUEUE}_${ARCHITECTURE} | md5sum | sed 's| .*||' | tail -c 9)"
    if [ -e cmsdist/cmssw-tool-conf.spec ] ; then
      echo "#PR ${PR_EXTERNAL_REPO}" >> cmsdist/cmssw-tool-conf.spec
    else
      echo "#PR ${PR_EXTERNAL_REPO}" >> cmsdist/cmssw-tool-conf.file
    fi
    UPLOAD_OPTS="--upload-tmp-repository ${PR_EXTERNAL_REPO}"
    if [ $(curl -s --head http://${CMSREP_IB_SERVER}/cmssw/repos/${CMS_WEEKLY_REPO}.${PR_EXTERNAL_REPO}/${ARCHITECTURE}/latest/ 2>&1 | head -1 | grep " 200 OK" |wc -l) -gt 0 ] ; then
      UPLOAD_OPTS="--sync-back"
      COMPILATION_CMD="${COMPILATION_CMD} --repository ${CMS_WEEKLY_REPO}.${PR_EXTERNAL_REPO}"
    else
      COMPILATION_CMD="${COMPILATION_CMD} --repository ${CMS_WEEKLY_REPO}"
    fi
    if [ "${SOURCE_FLAG}" != "" ] ; then UPLOAD_OPTS="${UPLOAD_OPTS} --force-upload" ; fi
    rm -rf $WORKSPACE/$BUILD_DIR
    [ -e cmsdist/fakesystem.spec ] && PKGS="fakesystem ${PKGS}"
    echo $COMPILATION_CMD build ${PKGS} > ${WORKSPACE}/cmsswtoolconf.log  # log the command to be run
    # run the command and both log it to file and display it
    (eval $COMPILATION_CMD build ${PKGS} && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
    echo_section 'END OF BUILD LOG'

    TEST_ERRORS=$(grep -E "Error [0-9]$" $WORKSPACE/cmsswtoolconf.log) || true
    GENERAL_ERRORS=$(grep "ALL_OK" $WORKSPACE/cmsswtoolconf.log) || true
    if [ -f "$WORKSPACE/$BUILD_DIR/tmp/bootstrap.log" ] ; then
      mv $WORKSPACE/$BUILD_DIR/tmp/bootstrap.log $WORKSPACE/bootstrap.log
    fi

    #upload packages build
    BLD_PKGS=$(ls $WORKSPACE/$BUILD_DIR/RPMS/${ARCHITECTURE}/ | grep '.rpm$' | cut -d+ -f2 | grep -v 'coral-debug' || true)
    if [ "${BLD_PKGS}" != "" ] ; then eval $COMPILATION_CMD ${UPLOAD_OPTS} upload ${BLD_PKGS} ; fi
    for d in bootstraptmp tmp RPMS SOURCES  SPECS  SRPMS WEB ; do
      rm -rf $WORKSPACE/$BUILD_DIR/${d} || true
    done

    echo 'CMSSWTOOLCONF_LOGS;OK,External Build Logs,See Log,externals' >> ${RESULTS_DIR}/toolconf.txt
    if [ $(grep 'RPM installation stderr' $WORKSPACE/cmsswtoolconf.log |wc -l) -gt 0 ] ; then
      echo 'CMSSWTOOLCONF_INSTALL;ERROR,Externals Installation,See Log,cmsswtoolconf.log' >> ${RESULTS_DIR}/toolconf.txt
    fi
    if [ "X$TEST_ERRORS" != X ] || [ "X$GENERAL_ERRORS" == X ]; then
      echo 'CMSSWTOOLCONF_RESULTS;ERROR,Externals compilation,See Log,cmsswtoolconf.log' >> ${RESULTS_DIR}/toolconf.txt
      ${CMS_BOT_DIR}/report-pull-request-results "PARSE_EXTERNAL_BUILD_FAIL" --unit-tests-file $WORKSPACE/cmsswtoolconf.log \
        --report-url ${PR_RESULT_URL} ${NO_POST} --report-file ${RESULTS_DIR}/10-report.res
      prepare_upload_results
      mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Failed to build externals"
      exit 0
    else
      echo 'CMSSWTOOLCONF_RESULTS;OK,Externals compilation,See Log,cmsswtoolconf.log' >> ${RESULTS_DIR}/toolconf.txt
    fi

    #Testing sourcing of cmsset_default: run only for CMSSW master IB/Proudcuton arch
    if $CMSSW_DEVEL_PROD_ARCH ; then
      CMSSET_DEFAULT_ERR=""
      mkdir $WORKSPACE/cmsset_default
      EL_OS=$(ls $WORKSPACE/$BUILD_DIR/common/cmssw-el* | sed 's|.*/common/cmssw-el|el|' | grep -v 'el5')
      for sh in bash sh zsh ; do
        for os in $EL_OS ; do
          echo "Checking cmsset_default.sh for $sh under $os" >>  $WORKSPACE/cmsset_default/run.log
          if ! $WORKSPACE/$BUILD_DIR/common/cmssw-$os -- $sh -e $WORKSPACE/$BUILD_DIR/cmsset_default.sh >>$WORKSPACE/cmsset_default/run.log 2>&1 ; then
            CMSSET_DEFAULT_ERR="${CMSSET_DEFAULT_ERR} $sh:$os"
            echo "Failed" >> $WORKSPACE/cmsset_default/run.log
            $WORKSPACE/$BUILD_DIR/common/cmssw-$os -- $sh -ex $WORKSPACE/$BUILD_DIR/cmsset_default.sh > $WORKSPACE/cmsset_default/${sh}-${os}.log 2>&1 || true
          else
            echo "OK" >> $WORKSPACE/cmsset_default/run.log
          fi
        done
      done
      if [ "${CMSSET_DEFAULT_ERR}" != "" ]  ; then
        echo "CMSSet_Default" >> ${RESULTS_DIR}/09-failed.res
        echo 'CMSSET_DEFAULT_RESULTS;ERROR,Environment setup,See Log,cmsset_default' >> ${RESULTS_DIR}/toolconf.txt
        echo "**Failed environment setup**: \`${CMSSET_DEFAULT_ERR}\`" >> ${RESULTS_DIR}/09-report.res
        #prepare_upload_results
        #mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Environment setup error"
        #exit 0
      else
        echo 'CMSSET_DEFAULT_RESULTS;OK,Environment setup,See Log,cmsset_default/run.log' >> ${RESULTS_DIR}/toolconf.txt
      fi
    fi

    OLD_DASGOCLIENT=$(dasgoclient --version  | tr ' ' '\n' | grep '^git=' | sed 's|^git=||')
    # Create an appropriate CMSSW area
    source $WORKSPACE/$BUILD_DIR/cmsset_default.sh
    if [ -e $WORKSPACE/$BUILD_DIR/common/dasgoclient ] ; then
      NEW_DASGOCLIENT=$($WORKSPACE/$BUILD_DIR/common/dasgoclient --version  | tr ' ' '\n' | grep '^git=' | sed 's|^git=||')
      XDAS=$(echo ${OLD_DASGOCLIENT} ${NEW_DASGOCLIENT} | tr ' ' '\n' | grep '^v' | sort | tail -1)
      if [ "${OLD_DASGOCLIENT}" != "${XDAS}" ] ; then TEST_DASGOCLIENT=true ; fi
    fi
    echo /cvmfs/cms.cern.ch > $WORKSPACE/$BUILD_DIR/etc/scramrc/links.db

    # To make sure we always pick scram from local area
    rm -f $CMSSW_IB/config/scram_basedir
    sver=$(grep '^lcg+SCRAMV1+' $WORKSPACE/cmsswtoolconf.log | head -1 | sed 's|^lcg+SCRAMV1+||;s| .*||')
    echo $sver  > $CMSSW_IB/config/scram_version
    config_tag=$(grep '%define *configtag *V' $WORKSPACE/cmsdist/scram-project-build.file | sed 's|.*configtag *V|V|;s| *||g')
    old_config_tag=$(cat $CMSSW_IB/config/config_tag)
    if [ -d $WORKSPACE/config ] ; then
      cp -r $WORKSPACE/config scram-buildrules
      config_tag="${config_tag}-01"
    else
      if [ "${old_config_tag}" != "${config_tag}" ] ; then
        git clone git@github.com:cms-sw/cmssw-config scram-buildrules
        pushd scram-buildrules
          git checkout ${config_tag}
        popd
      fi
    fi
    if [ -d scram-buildrules ] ; then
      echo ${config_tag} > $WORKSPACE/$CMSSW_IB/config/config_tag
      mv $CMSSW_IB/config/SCRAM $CMSSW_IB/config/SCRAM.orig
      mv scram-buildrules/SCRAM $CMSSW_IB/config/SCRAM
      if [ -d scram-buildrules/Projects/CMSSW ] ; then
        cp -f scram-buildrules/Projects/CMSSW/BuildFile.xml $CMSSW_IB/config/BuildFile.xml
        [ -e scram-buildrules/Projects/CMSSW/SCRAM_ExtraBuildRule.pm ] && cp -f scram-buildrules/Projects/CMSSW/SCRAM_ExtraBuildRule.pm $CMSSW_IB/config/SCRAM_ExtraBuildRule.pm
        (
          for x in SCRAM_COMPILER:DEFAULT_COMPILER PROJECT_GIT_HASH:CMSSW_GIT_HASH ENABLE_LTO:ENABLE_LTO ; do
            e=$(echo $x | sed 's|:.*||');
            k=$(echo $x | sed 's|.*:||');
            export $e=$(grep "$k" $CMSSW_IB/config/Self.xml | tr ' ' '\n' | grep '=' | tail -1 | sed 's|[^"]*"||;s|".*||');\
          done;
          perl -p -i -e 's|\@([^@]*)\@|$ENV{$1}|g' scram-buildrules/Projects/CMSSW/Self.xml
        )
        if [ "$MULTIARCH_OPTS" != "" ] ; then
          MULTIARCH_OPTSX=$(echo ${MULTIARCH_OPTS} | tr ',' ' ')
          DEFAULT_TARGET=$(cmssw_default_target $CMSSW_IB)
          sed -i -e "s| SCRAM_TARGETS=.*\"| SCRAM_TARGETS=\"${MULTIARCH_OPTSX}\"|" scram-buildrules/Projects/CMSSW/Self.xml
	  sed -i -e "s|</tool>| <runtime name=\"SCRAM_TARGET\" value=\"${DEFAULT_TARGET}\"/>\n <runtime name=\"USER_TARGETS_ALL\" value=\"1\"/>\n</tool>|" scram-buildrules/Projects/CMSSW/Self.xml
        fi
        cp scram-buildrules/Projects/CMSSW/Self.xml $CMSSW_IB/config/Self.xml
      else
        cp -f scram-buildrules/CMSSW_BuildFile.xml $CMSSW_IB/config/BuildFile.xml
        [ -e scram-buildrules/CMSSW_SCRAM_ExtraBuildRule.pm ] && cp -f scram-buildrules/CMSSW_SCRAM_ExtraBuildRule.pm $CMSSW_IB/config/SCRAM_ExtraBuildRule.pm
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
    echo "${CMS_WEEKLY_REPO}.${PR_EXTERNAL_REPO}/${TOOL_CONF_VERSION}" > $WORKSPACE/cmssw-tool-conf.txt
    echo "CMSSWTOOLCONF_VERSION;OK,External tool conf,See log,cmssw-tool-conf.txt" >> ${RESULTS_DIR}/toolconf.txt
    mv $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/${TOOL_CONF_VERSION}/tools/selected ${CTOOLS}
    if [ -e ${BTOOLS}/cmssw-config.xml ] ; then
      cp ${BTOOLS}/cmssw-config.xml ${CTOOLS}/
      if [ "${old_config_tag}" != "${config_tag}" ] ; then
        sed -i -e "s|${old_config_tag}|${config_tag}|" ${CTOOLS}/cmssw-config.xml || true
      fi
    fi
    #Copy extra available tools
    if [ -d $WORKSPACE/$CMSSW_IB/config/toolbox/${ARCHITECTURE}/tools/available -a -d $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/${TOOL_CONF_VERSION}/tools/available ] ; then
      mv $WORKSPACE/$CMSSW_IB/config/toolbox/${ARCHITECTURE}/tools/{available,available.backup}
      mv $WORKSPACE/$BUILD_DIR/$ARCHITECTURE/cms/cmssw-tool-conf/${TOOL_CONF_VERSION}/tools/available $WORKSPACE/$CMSSW_IB/config/toolbox/${ARCHITECTURE}/tools/available
    fi

    #Generate External Tools Status
    echo '<html><head><link href="https://netdna.bootstrapcdn.com/bootstrap/3.1.1/css/bootstrap.min.css" rel="stylesheet"></head>' > $WORKSPACE/upload/external-tools.html
    echo '<body><h2>External tools build Statistics</h2><br/><table class="table table-striped"><tr><td>Tool Name</td><td>#Files(new)</td><td>#Files(old)</td><td>Size(new)</td><td>Size(old)</td></tr>' >> $WORKSPACE/upload/external-tools.html
    for pkg in $(find ${WORKSPACE}/${BUILD_DIR}/BUILD/${ARCHITECTURE} -maxdepth 3 -mindepth 3 -type d | sed "s|$WORKSPACE/$BUILD_DIR/BUILD/||" | sort) ; do
      ltpath="${WORKSPACE}/${BUILD_DIR}/${pkg}"
      [ -d ${ltpath} ] || continue
      l_tc=$(find ${ltpath} -follow | wc -l)
      l_ts=$(du -shD ${ltpath} | awk '{print $1}')
      tdir=$(dirname $pkg)
      rtpath=$(grep -R ${tdir} ${BTOOLS} | grep '_BASE\|CMSSW_SEARCH_PATH' | tail -1 | sed 's|.* default="||;s|".*||')
      if [ "${rtpath}" = "" ] || [ ! -d "${rtpath}" ] ; then
        r_tc=0
        r_ts=0
      else
        r_tc=$(find ${rtpath} -follow | wc -l)
        r_ts=$(du -shD ${rtpath} | awk '{print $1}')
      fi
      tool=$(basename $tdir)
      echo "<tr><td>${tool}</td><td>$l_tc</td><td>$r_tc</td><td>$l_ts</td><td>$r_ts</td></tr>" >> $WORKSPACE/upload/external-tools.html
    done
    echo "</table></body></html>" >> $WORKSPACE/upload/external-tools.html
    echo 'CMSSWTOOLCONF_STATS;OK,External Build Stats,See Log,external-tools.html' >> ${RESULTS_DIR}/toolconf.txt
    set +x
    TOOL_SETUP=true
    if [ "X$BUILD_FULL_CMSSW" != "Xtrue" ] ; then
      # Setup all the toolfiles previously built
      DEP_NAMES=
      if [ -e "${BTOOLS}/cmssw.xml" ] ; then cp ${BTOOLS}/cmssw.xml ${CTOOLS}/cmssw.xml ; fi
      RMV_CMSSW_EXTERNAL="$(ls -d $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/*-remove-release-external-lib 2>/dev/null || true)"
      if [ "${RMV_CMSSW_EXTERNAL}" != "" ] ; then
        chmod +x ${RMV_CMSSW_EXTERNAL}
      fi
      DEP_NAMES=""
      #Fix for SCRAMV2 based releases were tools can have different capitalizations
      ALL_NEW_TOOLS=$(ls ${CTOOLS}/ | tr '[A-Z]\n' '[a-z] ')
      #In some releases libjpeg-turbo tool exists via libjpg
      [ $(echo " ${ALL_NEW_TOOLS} " | grep " libjpg.xml " | wc -l) -gt 0 ] && ALL_NEW_TOOLS="${ALL_NEW_TOOLS} libjpeg-turbo.xml"
      for xml in $(ls ${BTOOLS}/*.xml) ; do
        name=$(basename $xml)
        lcname=$(echo $name | tr '[A-Z]' '[a-z]')
        if [ $(echo " ${ALL_NEW_TOOLS} " | grep " ${lcname} " |wc -l) -eq 0 ] ; then
          tool=$(echo $name | sed 's|.xml$||')
          echo "Removed tool $name"
          DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
        fi
      done
      if [ "${DEP_NAMES}" != "" ] ; then
        CMSSW_DEP=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
        DEP_NAMES=""
        echo "CMSSW_DEP=${CMSSW_DEP}"
      fi
      rm -rf $WORKSPACE/$CMSSW_IB/.SCRAM/$ARCHITECTURE/tools
      for xml in $(ls ${CTOOLS}/*.xml) ; do
        name=$(basename $xml)
        tool=$(echo $name | sed 's|.xml$||')
        echo "Checking tool $tool ($xml)"
        if [ ! -e ${BTOOLS}/$name ] ; then
          scram setup $xml >> $WORKSPACE/scram-tool-setup.log 2>&1 || TOOL_SETUP=false
          continue
        fi
        echo "Checking ${name}"
		    if ! diff -u \
             <(sed -r 's|"/([^/]+/)+([^"]+)"|"/PATH/\2"|g; s|^[[:space:]]+||; s|[[:space:]\r]+$||; s|[[:space:]]+| |g' ${xml}) \
             <(sed -r 's|"/([^/]+/)+([^"]+)"|"/PATH/\2"|g; s|^[[:space:]]+||; s|[[:space:]\r]+$||; s|[[:space:]]+| |g' ${BTOOLS}/$name)  ; then
          DEP_NAMES="$DEP_NAMES echo_${tool}_USED_BY"
          echo "  Tool changed/updated: ${name}"
        fi
      done
      sed -i -e 's|.*/lib/python2.7/site-packages" .*||;s|.*/lib/python3.6/site-packages" .*||' ../config/Self.xml
      touch $CTOOLS/*.xml
      (scram setup && scram setup self && rm -rf $WORKSPACE/$CMSSW_IB/external && scram build -r echo_CXX) >> $WORKSPACE/scram-tool-setup.log 2>&1 || TOOL_SETUP=false
      echo "DEP_NAMES=${DEP_NAMES}"
      if $TOOL_SETUP ; then
        if [ "${DEP_NAMES}" != "" ] ; then
          CMSSW_DEPx=$(scram build ${DEP_NAMES} | tr ' ' '\n' | grep '^cmssw/\|^self/' | cut -d"/" -f 2,3 | sort | uniq)
          CMSSW_DEP=$(echo ${CMSSW_DEP} ${CMSSW_DEPx} | tr ' ' '\n' | sort | uniq)
        fi
        if [ -e ${BTOOLS}/cmsswdata.xml ] ; then
          CMSSW_DATA_PKGS=$(diff -u ${CTOOLS}/cmsswdata.xml ${BTOOLS}/cmsswdata.xml | grep 'CMSSW_DATA_PACKAGE=' |  grep -E '^[-+]' | sed 's|.*CMSSW_DATA_PACKAGE="||;s|=.*||' | sort | uniq)
          if [ "${CMSSW_DATA_PKGS}" != "" ] ; then CMSSW_DEP="${CMSSW_DEP} ${CMSSW_DATA_PKGS}"; fi
        fi
        echo "Final CMSSW_DEP=${CMSSW_DEP}"
        if [ "$CMSSW_DEP" = "" ] ; then CMSSW_DEP="FWCore/Version" ; fi
      fi
    else
      rm -f $WORKSPACE/$CMSSW_IB/.SCRAM/$ARCHITECTURE/Environment
      rm -rf $WORKSPACE/$CMSSW_IB/.SCRAM/$ARCHITECTURE/tools
      touch $CTOOLS/*.xml $WORKSPACE/$CMSSW_IB/config/Self.xml
      scram tool remove cmssw || true
      (scram setup && scram setup self && rm -rf $WORKSPACE/$CMSSW_IB/external && scram b clean && scram build -r echo_CXX)  > $WORKSPACE/scram-tool-setup.log 2>&1 || TOOL_SETUP=false
      CMSSW_DEP="*"
      SKIP_STATIC_CHECKS=true
    fi
    if ! $TOOL_SETUP ; then
      echo 'SCRAM_TOOLS_SETUP;ERROR,Scram tools setup,See Log,scram-tool-setup.log' >> ${RESULTS_DIR}/scramtools.txt
      prepare_upload_results
      mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Failed to setup externals"
      exit 0
    fi
    eval $(scram runtime -sh)
    set -x
    echo $LD_LIBRARY_PATH
    if [ -e $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/00-nvidia-drivers ] ; then
      SCRAM=scram bash -ex $WORKSPACE/$CMSSW_IB/config/SCRAM/hooks/runtime/00-nvidia-drivers || true
    fi
    git cms-init --upstream-only
    pushd $WORKSPACE/$CMSSW_IB/src
      if [ "X$BUILD_FULL_CMSSW" = "Xtrue" ] ; then
        git checkout $(echo "${CONFIG_LINE}" | sed 's|.*RELEASE_BRANCH=||;s|;.*||')
        echo '/*/' >> .git/info/sparse-checkout
        git read-tree -mu HEAD
      else
        git cms-checkout-topic --ssh $(git branch | grep  '^  *CMSSW_') 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
        git cms-checkdeps -A -a 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
        git cms-addpkg --ssh "$CMSSW_DEP" 2>&1 | tee -a $WORKSPACE/cmsswtoolconf.log
      fi
    popd
    rm -rf $WORKSPACE/$CMSSW_IB/external
    scram b clean
    scram b -r echo_CXX
fi # end of build external
echo_section "end of build external"

# This part responsible for testing CMSSW
echo_section "Testing CMSSW"
voms-proxy-init -voms cms -valid 24:00 || true  # To get access to jenkins artifact machine

### to know at the end of the tests if everything went ok
ALL_OK=true
BUILD_OK=true
UNIT_TESTS_OK=true
RELVALS_OK=true
ADDON_OK=true
CLANG_BUILD_OK=true
PYTHON3_BUILD_OK=true
RUN_TESTS=true

cd $WORKSPACE/$CMSSW_IB

set +x
eval $(scram run -sh)
set -x
echo $LD_LIBRARY_PATH | tr ':' '\n'
BUILD_LOG_DIR="${CMSSW_BASE}/tmp/${SCRAM_ARCH}/cache/log"
USER_FLAGS=""
if $DISABLE_CMS_DEPRECATED ;  then
  #USER_FLAGS="USER_CXXFLAGS=-DUSE_CMS_DEPRECATED"
  ANALOG_OPT="--ignoreWarning=Wdeprecated-declarations"
fi
ANALOG_CMD="scram build outputlog && (${CMS_PYTHON_TO_USE} $CMS_BOT_DIR/buildLogAnalyzer.py ${ANALOG_OPT} --logDir ${BUILD_LOG_DIR}/src || true)"
OK_ANALOG_CMD="true && (${CMS_PYTHON_TO_USE} $CMS_BOT_DIR/buildLogAnalyzer.py ${ANALOG_OPT} --logDir ${BUILD_LOG_DIR}/src || true)"

cd $WORKSPACE/$CMSSW_IB/src
git config --global --replace-all merge.renamelimit 2500 || true

GIT_MERGE_RESULT_FILE=$WORKSPACE/git-merge-result
RECENT_COMMITS_FILE=$WORKSPACE/git-recent-commits.json
RECENT_COMMITS_LOG_FILE=$WORKSPACE/git-log-recent-commits
echo '{}' > $RECENT_COMMITS_FILE
# use the branch name if necesary
touch $WORKSPACE/changed-files
if [ ! -d $WORKSPACE/cms-prs ]  ; then git clone --depth 1 git@github.com:cms-sw/cms-prs $WORKSPACE/cms-prs ; fi
if ! $CMSDIST_ONLY ; then # If a CMSSW specific PR was specified #
  if $USE_IB_TAG ; then git cms-init --upstream-only $CMSSW_IB ; fi

  # this is to test several pull requests at the same time
  for PR in $( echo ${PULL_REQUESTS} | tr ' ' '\n' | grep "/cmssw#"); do
    echo 'I will add the following pull request to the test'
    PR_NR=$(echo ${PR} | sed 's/.*#//' )
    (git cms-merge-topic --debug --ssh -u ${CMSSW_ORG}:${PR_NR} && echo 'ALL_OK') 2>&1 | tee -a $GIT_MERGE_RESULT_FILE
  done

  if grep 'Automatic merge failed' $GIT_MERGE_RESULT_FILE; then
    echo "This pull request cannot be automatically merged, could you please rebase it?" > ${RESULTS_DIR}/10-report.res
    echo "You can see the log for git cms-merge-topic here: ${PR_RESULT_URL}/git-merge-result" >> ${RESULTS_DIR}/10-report.res
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Merge: Unable to merge CMSSW PRs"
    exit 0
  fi

  if grep "Couldn't find remote ref" $GIT_MERGE_RESULT_FILE; then
    echo "I had the issue <pre>could not find remote ref refs/pull/${PR_NUMBER}/head</pre>" > ${RESULTS_DIR}/10-report.res
    echo 'Please restart the tests in jenkins providing the complete branch name' >> ${RESULTS_DIR}/10-report.res
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Merge: Unable to find remote reference."
    exit 0
  fi

  git diff --name-only $CMSSW_VERSION > $WORKSPACE/changed-files

  # look for any other error in general
  if ! grep "ALL_OK" $GIT_MERGE_RESULT_FILE; then
    echo "There was an issue with git-cms-merge-topic you can see the log here: ${PR_RESULT_URL}/git-merge-result" > ${RESULTS_DIR}/10-report.res
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "Merge: Unknow error while merging."
    exit 0
  fi

  if [[ "${PRODUCTION_RELEASE}" == "true" && "${PULL_REQUEST}" == *"/cmssw#"* ]]; then
    pushd ${CMSSW_BASE}
      mv src src.tmp && mkdir src
      cd src
      THRDS=""
      git cms-init --upstream-only && git checkout -b codechecks $CMSSW_IB
      git repack -h 2>&1 | grep '\-\-threads' && THRDS="--threads ${NCPU}" || true
      git repack -a -d ${THRDS}
      git repack -a -d ${THRDS}
      OSIZE=$(du -sk .git/objects/pack | sed 's|\s.*||')
      git cms-merge-topic --debug --ssh -u ${CMSSW_ORG}:${PR_NUMBER}
      git repack -d ${THRDS}
      NSIZE=$(du -sk .git/objects/pack | sed 's|\s.*||')
      let DSIZE=${NSIZE}-${OSIZE} || DSIZE=0
      if [ $DSIZE -gt 0 ]; then echo "**Size**: This PR adds an extra ${DSIZE}KB to repository" > ${RESULTS_DIR}/09-git-repo-size-report.res; fi
      cd ..
      rm -rf src && mv src.tmp src
    popd
  fi

  #############################################
  # Check if there are unwanted commits that came with the merge.
  ############################################
  merged_prs=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep "/cmssw#" | sed 's|.*#||' | tr '\n' ',')
  $SCRIPTPATH/get-merged-prs.py -r cms-sw/cmssw -i "${merged_prs}" -s $CMSSW_VERSION -e HEAD -g $CMSSW_BASE/src/.git -c $WORKSPACE/cms-prs -o $RECENT_COMMITS_FILE
  echo "##### CMSSW Extra merges #####" >> $RECENT_COMMITS_LOG_FILE
  git log ${CMSSW_IB}..HEAD --merges 2>&1 | tee -a $RECENT_COMMITS_LOG_FILE

  if [ $DO_MB_COMPARISON -a $(grep 'Geometry' $WORKSPACE/changed-files | wc -l) -gt 0 ] ; then
    has_jenkins_artifacts material-budget/$CMSSW_IB/$SCRAM_ARCH/Images || DO_MB_COMPARISON=false
  else
    DO_MB_COMPARISON=false
  fi
elif [ "X$BUILD_FULL_CMSSW" = "Xtrue" ] ; then
  $SCRIPTPATH/get-merged-prs.py -r cms-sw/cmssw -s $CMSSW_VERSION -e HEAD -g $CMSSW_BASE/src/.git -c $WORKSPACE/cms-prs -o $RECENT_COMMITS_FILE
  echo "##### CMSSW Extra merges #####" >> $RECENT_COMMITS_LOG_FILE
  git log ${CMSSW_IB}..HEAD --merges 2>&1 | tee -a $RECENT_COMMITS_LOG_FILE
fi
if ! scram build -r echo_CXX > $WORKSPACE/build.log 2>&1 ; then
    echo "**ERROR**: SCRAM failed to generate build rules, there might be syntax errors in modified BuildFiles." > ${RESULTS_DIR}/10-report.res
    echo "SCRAM_BUILD_CXX;ERROR,SCRAM Build Rules,See Log,build.log" > ${RESULTS_DIR}/scramb.txt
    prepare_upload_results
    mark_commit_status_all_prs '' 'error' -u "${PR_RESULT_URL}" -d "There might be syntax errors in BuildFiles."
    exit 0
fi
if ${BUILD_EXTERNAL} ; then
  pushd $WORKSPACE/cmsdist
    CMSDIST_REL_TAG=$(git tag | grep '^'ALL/${CMSSW_VERSION}/${SCRAM_ARCH}'$' || true)
    if [ "${CMSDIST_REL_TAG}" != "" ] ; then
      merged_prs=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep "/cmsdist#" | sed 's|.*#||' | tr '\n' ',')
      $SCRIPTPATH/get-merged-prs.py -r cms-sw/cmsdist -i "${merged_prs}" -s ${CMSDIST_REL_TAG} -e HEAD -g $WORKSPACE/cmsdist/.git -c $WORKSPACE/cms-prs -o $RECENT_COMMITS_FILE
      echo "##### CMSDIST Extra merges #####" >> $RECENT_COMMITS_LOG_FILE
      git log ${CMSDIST_REL_TAG}..HEAD --merges 2>&1 | tee -a $RECENT_COMMITS_LOG_FILE
    fi
  popd
fi
$CMS_BOT_DIR/report-pull-request-results MERGE_COMMITS --recent-merges $RECENT_COMMITS_FILE --report-url ${PR_RESULT_URL} --report-file ${RESULTS_DIR}/09-report.res ${REPORT_OPTS}

# Don't do the following if we are only testing CMSDIST PR
if [ "X$CMSDIST_ONLY" == Xfalse ]; then
  git log --oneline --merges ${CMSSW_VERSION}..
fi

# #############################################
# test compilation with Clang
# ############################################
echo 'test clang compilation'

NEED_CLANG_TEST=false
if cat $CONFIG_MAP | grep $CMSSW_QUEUE | grep PRS_TEST_CLANG= | grep SCRAM_ARCH=$ARCHITECTURE; then
  NEED_CLANG_TEST=true
fi

if [ "X$TEST_CLANG_COMPILATION" = Xtrue -a $NEED_CLANG_TEST = true -a "X$CMSSW_PR" != X -a "$SKIP_STATIC_CHECKS" = "false" ]; then
  #first, add the command to the log
  CLANG_USER_CMD="USER_CUDA_FLAGS='--expt-relaxed-constexpr' USER_CXXFLAGS='-Wno-register -fsyntax-only' /usr/bin/time -v scram build -k -j ${NCPU2} COMPILER='llvm compile'"
  CLANG_CMD="scram b vclean && ${CLANG_USER_CMD} BUILD_LOG=yes"
  echo $CLANG_USER_CMD > $WORKSPACE/buildClang.log

  (eval $CLANG_CMD && echo 'ALL_OK') >>$WORKSPACE/buildClang.log 2>&1 || true
  #always run ${ANALOG_CMD} to print out the compile command which are normally printed when on runs full build
  #in llvm case we are only doing compile (withoutlinking)
  (eval ${ANALOG_CMD})    >>$WORKSPACE/buildClang.log 2>&1 || true

  TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/buildClang.log` || true
  GENERAL_ERRORS=`grep "^ALL_OK$" $WORKSPACE/buildClang.log` || true

  if [ -d ${BUILD_LOG_DIR}/html ] ; then
    mv ${BUILD_LOG_DIR}/html $WORKSPACE/clang-logs
    echo 'CLANG_LOG;OK,Clang warnings summary,See Log,clang-logs' >> ${RESULTS_DIR}/clang.txt
  fi

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when testing compilation with clang"
    echo 'CLANG_COMPILATION_RESULTS;ERROR,Clang Compilation,See Log,buildClang.log' >> ${RESULTS_DIR}/clang.txt
    RUN_TESTS=false
    ALL_OK=false
    CLANG_BUILD_OK=false
  else
    echo "the clang compilation had no errors/warnings!!"
    echo 'CLANG_COMPILATION_RESULTS;OK,Clang Compilation,See Log,buildClang.log' >> ${RESULTS_DIR}/clang.txt
  fi
fi

#Do QA checks
#Code Rules
QA_RES="NOTRUN"
if [ "X$CMSDIST_ONLY" == "Xfalse" -a "X${CODE_RULES}" = "Xtrue" -a "$SKIP_STATIC_CHECKS" = "false" ]; then # If a CMSSW specific PR was specified
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
      pycmd=python2
      if ! python2 -c 'import Utilities.ReleaseScripts.cmsCodeRules.config' >/dev/null 2>&1 ; then pycmd=python3 ; fi
      $pycmd -c "from Utilities.ReleaseScripts.cmsCodeRules.config import Configuration as x;print(x['$CRULE']['description'])" >> $r.new || true
      echo "" >> $r.new
      cat $r >> $r.new
      mv $r.new $r
      QA_RES="ERROR"
    fi
  done
  echo "CODE_RULES;${QA_RES},CMSSW Code Rules,See Logs,codeRules" >> ${RESULTS_DIR}/coderules.txt
fi

#Do Python3 checks
DO_PYTHON3=false
if $IS_DEV_BRANCH ; then
  if [ $(echo "${CONFIG_LINE}" | tr ';' '\n' | grep 'ADDITIONAL_TESTS=' | tr '=,' '\n\n' | grep '^python3$' | wc -l) -gt 0 ] ; then
    DO_PYTHON3=true
  fi
fi
if $DO_PYTHON3 ; then
  PYTHON3_RES="OK"
  CMD_python=$(which python3) scram b -r -k -j ${NCPU} CompilePython > $WORKSPACE/python3.log 2>&1 || true
  if [ $(grep ' Error compiling ' $WORKSPACE/python3.log | wc -l) -gt 0 ] ; then
    PYTHON3_RES="ERROR"
    PYTHON3_BUILD_OK=false
    RUN_TESTS=false
    ALL_OK=false
  fi
  echo "PYTHON3_CHECKS;${PYTHON3_RES},Python3 Checks,See Log,python3.log" >> ${RESULTS_DIR}/python3.txt
fi

#
# Static checks
#
if [ "X$DO_STATIC_CHECKS" = "Xtrue" -a "X$CMSSW_PR" != X -a "$RUN_TESTS" = "true" -a "$SKIP_STATIC_CHECKS" = "false" ]; then
  echo 'STATIC_CHECKS;OK,Static checks outputs,See Static Checks,llvm-analysis' >> ${RESULTS_DIR}/static.txt
  echo '--------------------------------------'
  pushd $WORKSPACE/$CMSSW_IB
  git cms-addpkg --ssh Utilities/StaticAnalyzers
  mkdir $WORKSPACE/llvm-analysis
  USER_CXXFLAGS='-Wno-register -DEDM_ML_DEBUG -w' SCRAM_IGNORE_PACKAGES="Fireworks/% Utilities/StaticAnalyzers" USER_LLVM_CHECKERS="-enable-checker threadsafety -enable-checker cms -enable-checker deprecated -disable-checker cms.FunctionDumper" \
    scram b -k -j ${NCPU2} checker SCRAM_IGNORE_SUBDIRS=test >>$WORKSPACE/llvm-analysis/runStaticChecks.log 2>&1 || true
  cp -R $WORKSPACE/$CMSSW_IB/llvm-analysis/*/* $WORKSPACE/llvm-analysis || true
  if [ $(find $WORKSPACE/$CMSSW_IB -maxdepth 1 -mindepth 1 -name 'clang_other_error_*' -type f | wc -l) -gt 0 ] ;  then
    mkdir $WORKSPACE/llvm-analysis/failures
    find $WORKSPACE/$CMSSW_IB -maxdepth 1 -mindepth 1 -name 'clang_other_error_*' -type f | xargs -i mv '{}' $WORKSPACE/llvm-analysis/failures/
  fi
  if $IS_DEV_BRANCH && [ $(grep ': error: ' $WORKSPACE/llvm-analysis/runStaticChecks.log | wc -l) -gt 0 ] ; then
    echo "EDM_ML_DEBUG_CHECKS;ERROR,Static Check build log,See Log,llvm-analysis/runStaticChecks.log" >> ${RESULTS_DIR}/static.txt
  else
    echo "EDM_ML_DEBUG_CHECKS;OK,Static Check build log,See Log,llvm-analysis/runStaticChecks.log" >> ${RESULTS_DIR}/static.txt
  fi
  if $IS_DEV_BRANCH ;then 
    curl -s -L https://patch-diff.githubusercontent.com/raw/${PR_REPO}/pull/${PR_NUMBER}.patch | grep '^diff --git ' | sed 's|.* a/||;s|  *b/.*||' | sort | uniq > $WORKSPACE/all-changed-files.txt
    touch $WORKSPACE/llvm-analysis/esrget-sa.txt
    grep ': warning: ' $WORKSPACE/llvm-analysis/runStaticChecks.log | grep -f $WORKSPACE/all-changed-files.txt | grep edm::eventsetup::EventSetupRecord::get | sort -u > $WORKSPACE/llvm-analysis/esrget-sa.txt
    touch $WORKSPACE/llvm-analysis/legacy-mod-sa.txt
    grep ': warning: ' $WORKSPACE/llvm-analysis/runStaticChecks.log | grep -f $WORKSPACE/all-changed-files.txt | grep 'inherits from edm::EDProducer,edm::EDFilter,edm::EDAnalyzer, or edm::OutputModule' | sort -u > $WORKSPACE/llvm-analysis/legacy-mod-sa.txt
    if [ $(cat $WORKSPACE/llvm-analysis/esrget-sa.txt | wc -l) -gt 0 ] ; then
      echo "STATIC_CHECK_ESRGET;ERROR,Static analyzer EventSetupRecord::get warnings,See warnings log,llvm-analysis/esrget-sa.txt" >> ${RESULTS_DIR}/static.txt
      echo "**CMS StaticAnalyzer warnings**: There are $(cat $WORKSPACE/llvm-analysis/esrget-sa.txt | wc -l) EventSetupRecord::get warnings. See ${PR_RESULT_URL}/llvm-analysis/esrget-sa.txt for details." >> ${RESULTS_DIR}/09-report.res
    fi
    if  [ $(cat $WORKSPACE/llvm-analysis/legacy-mod-sa.txt | wc -l) -gt 0 ] ; then
      echo "STATIC_CHECK_LEGACY;ERROR,Static analyzer inherits from legacy modules warnings,See warnings log,llvm-analysis/legacy-mod-sa.txt" >> ${RESULTS_DIR}/static.txt
      echo "**CMS StaticAnalyzer warnings**: There are $(cat $WORKSPACE/llvm-analysis/legacy-mod-sa.txt | wc -l) inherits from legacy modules warnings. See ${PR_RESULT_URL}/llvm-analysis/legacy-mod-sa.txt for details." >> ${RESULTS_DIR}/09-report.res
    fi
  fi
  echo 'END OF STATIC CHECKS'
  echo '--------------------------------------'
  popd
fi

scram build clean
if [ "X$BUILD_FULL_CMSSW" != "Xtrue" -a -d $LOCALRT/src/.git ] ; then git cms-checkdeps -A -a || true ; fi
[ -e $LOCALRT/src/Utilities/RelMon ] || git cms-addpkg Utilities/RelMon
sed -i -e 's|\.\./RelMonSummary.html|RelMonSummary.html|' $LOCALRT/src/Utilities/RelMon/python/directories2html.py || true
grep -R -l 'To the DQM GUI' $LOCALRT/src/Utilities/RelMon | grep -v '\.pyc$' | xargs --no-run-if-empty sed -i -e '/To the DQM GUI/d' || true

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
  rm -rf $WORKSPACE/$CMSSW_IB/poison
fi
# #############################################
# test header checks tests
# ############################################
CHK_HEADER_OK=true
if $IS_DEV_BRANCH ; then
  if [ "X${CHECK_HEADER_TESTS}" = "Xtrue" -a -f $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.chk_headers ] ; then
    IGNORE_HDRS="%.i"
    if [ -e "$WORKSPACE/$RELEASE_FORMAT/src/TrackingTools/GsfTools/interface/MultiGaussianStateCombiner.h" ] ; then
      IGNORE_HDRS="TrackingTools/GsfTools/interface/MultiGaussianStateCombiner.h %.i"
    fi
    COMPILATION_CMD="scram b vclean && USER_CHECK_HEADERS_IGNORE='${IGNORE_HDRS}' /usr/bin/time -v scram build -k -j ${NCPU} check-headers"
    echo $COMPILATION_CMD > $WORKSPACE/headers_chks.log
    (eval $COMPILATION_CMD && echo 'ALL_OK') >>$WORKSPACE/headers_chks.log 2>&1 || true
    echo 'END OF HEADER CHEKS LOG'
    for h in $(grep '^gmake: ' $WORKSPACE/headers_chks.log | grep '\.chk_header' | sed  -e "s|.*tmp/$ARCHITECTURE/*||;s|^check_header/*||;s|^src/*||;s|].*||;s|\.chk_header.*||;s|/src/[^/]*/|/interface/|") ; do
      [ $(grep -E "/$h(:[0-9][0-9]*)*: error: #error " $WORKSPACE/headers_chks.log | wc -l) -gt 0 ] &&  continue
      echo $h >> ${WORKSPACE}/headers_with_error.log
    done
    CHK_HEADER_LOG_RES="OK"
    CHK_HEADER_OK=true
    if [ -e ${WORKSPACE}/headers_with_error.log ] ; then
      CHK_HEADER_LOG_RES="ERROR"
      CHK_HEADER_OK=false
      ALL_OK=false
      echo "Header files  with errors" > ${WORKSPACE}/headers_chks.log1
      cat ${WORKSPACE}/headers_with_error.log >> ${WORKSPACE}/headers_chks.log1
      echo "" >> ${WORKSPACE}/headers_chks.log1
      echo "Full build log" >> ${WORKSPACE}/headers_chks.log1
      cat $WORKSPACE/headers_chks.log >> $WORKSPACE/headers_chks.log1
      rm -f $WORKSPACE/headers_chks.log ${WORKSPACE}/headers_with_error.log
      mv $WORKSPACE/headers_chks.log1 $WORKSPACE/headers_chks.log
    fi
    echo "HEADER_CHECKS;${CHK_HEADER_LOG_RES},Header Consistency,See Log,headers_chks.log" >> ${RESULTS_DIR}/header.txt
  fi
fi

##########################################
# Checkout full cmssw is requested
##########################################
if [ "${BUILD_FULL_CMSSW}-${BUILD_EXTERNAL}" = "true-false" ] ; then
  if [ -d  $LOCALRT/src/.git ] ; then
    pushd $LOCALRT/src
      echo '/*/' >> .git/info/sparse-checkout
      git read-tree -mu HEAD
    popd
  else
    git cms-addpkg '*'
  fi
  set +x
  rm -rf $WORKSPACE/$CMSSW_IB/poison
  rm -f $WORKSPACE/$CMSSW_IB/.SCRAM/$ARCHITECTURE/Environment
  touch $WORKSPACE/$CMSSW_IB/config/toolbox/${ARCHITECTURE}/tools/selected/*.xml $WORKSPACE/$CMSSW_IB/config/Self.xml
  scram tool remove cmssw || true
  scram setup
  scram setup self
  rm -rf $WORKSPACE/$CMSSW_IB/external
  scram b clean
  scram build -r echo_CXX
  eval $(scram run -sh)
  set -x 
fi

# #############################################
# test compilation with GCC
# ############################################
if [ "X$EXTRA_CMSSW_PACKAGES" != "X" ] ; then
  git cms-addpkg $(echo "${EXTRA_CMSSW_PACKAGES}" | tr ',' ' ') || true
fi
mark_commit_status_all_prs '' 'pending' -u "${BUILD_URL}" -d "Building CMSSW" || true
if [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep '^MULTI_MICROARCHS$' | wc -l) -gt 0 ] ; then
  scram build enable-multi-targets || true
fi
COMPILATION_CMD="scram b vclean && BUILD_LOG=yes $USER_FLAGS /usr/bin/time -v scram b ${BUILD_VERBOSE} -k -j ${NCPU}"
if [ $(grep '^edm_checks:' $WORKSPACE/$CMSSW_IB/config/SCRAM/GMake/Makefile.rules | wc -l) -gt 0 ] ; then
  COMPILATION_CMD="scram b vclean && BUILD_LOG=yes SCRAM_NOEDM_CHECKS=yes $USER_FLAGS /usr/bin/time -v scram build ${BUILD_VERBOSE} -k -j ${NCPU} && scram b -k -j ${NCPU} edm_checks"
fi
echo $COMPILATION_CMD > $WORKSPACE/build.log
(eval $COMPILATION_CMD && echo 'ALL_OK') >>$WORKSPACE/build.log 2>&1 || true
if [ $(grep "^ALL_OK$" $WORKSPACE/build.log |wc -l) -gt 0 ] ; then
  (eval ${OK_ANALOG_CMD}) >>$WORKSPACE/build.log 2>&1 || true
else
  (eval ${ANALOG_CMD})    >>$WORKSPACE/build.log 2>&1 || true
fi
if [ -d ${BUILD_LOG_DIR}/html ] ; then mv ${BUILD_LOG_DIR}/html ${WORKSPACE}/build-logs ; fi
echo 'END OF BUILD LOG'
echo '--------------------------------------'

TEST_ERRORS=`grep -E "^gmake: .* Error [0-9]" $WORKSPACE/build.log` || true
GENERAL_ERRORS=`grep "^ALL_OK$" $WORKSPACE/build.log` || true

rm -f $WORKSPACE/deprecated-warnings.log
get_compilation_warnings $WORKSPACE/build.log > $WORKSPACE/all-warnings.log

pushd $CMSSW_BASE
scram b echo_SCRAM_TOOL_HOME
SCRAM_TOOL_HOME=`scram b echo_SCRAM_TOOL_HOME 2>/dev/null | tail -1 | cut -d' ' -f3`
mkdir -p etc/dependencies
SCRAM_VER=$(cat config/scram_version)
if [ $(echo ${SCRAM_VER} | grep '^V3' | wc -l) -gt 0 ] ; then
  SCRAM_TOOL_HOME=$SCRAM_TOOL_HOME ./config/SCRAM/findDependencies.py -rel `pwd` -arch ${SCRAM_ARCH}
else
  perl config/SCRAM/findDependencies.pl -rel `pwd` -arch ${SCRAM_ARCH} -scramroot $SCRAM_TOOL_HOME
fi
[ -f etc/dependencies/usedby.out ] && cp etc/dependencies/usedby.out $WORKSPACE/usedby.txt
process_changed_files "$WORKSPACE/changed-files" "$WORKSPACE/full-list-of-changed-files.txt"
popd

for i in $(get_warnings_files $WORKSPACE/all-warnings.log $WORKSPACE/full-list-of-changed-files.txt) ; do
  echo $i > $WORKSPACE/warning.log
  grep ": warning: " $WORKSPACE/all-warnings.log | grep "/$i" >> $WORKSPACE/warning.log
  if $IS_DEV_BRANCH ; then
    if [ $(grep ": warning: " $WORKSPACE/warning.log | grep 'Wdeprecated-declarations' | wc -l) -gt 0 ] ; then
      cat $WORKSPACE/warning.log >>  $WORKSPACE/deprecated-warnings.log
    fi
  fi
  if [ $(grep ": warning: " $WORKSPACE/warning.log | grep -v 'Wdeprecated-declarations' | wc -l) -gt 0 ] ; then
    cat $WORKSPACE/warning.log >> $WORKSPACE/new-build-warnings.log
  fi
  rm -f $WORKSPACE/warning.log
done
if [ -e $WORKSPACE/new-build-warnings.log ]  ; then
    echo 'BUILD_NEW_WARNINGS;ERROR,Compilation Warnings to fix,See Log,new-build-warnings.log' >> ${RESULTS_DIR}/buildrules.txt
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^BUILD-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      BUILD_OK=false
    fi
fi
if [ -e $WORKSPACE/deprecated-warnings.log ] ; then
  echo 'BUILD_DEPRECATED_WARNINGS;ERROR,CMS Deprecated Warnings,See Log,deprecated-warnings.log' >> ${RESULTS_DIR}/buildrules.txt
  echo "**CMS deprecated warnings**: $(cat ${WORKSPACE}/deprecated-warnings.log | grep 'Wdeprecated-declarations' | wc -l) CMS deprecated warnings found, see [summary page](${PR_RESULT_URL}/deprecated-warnings.log) for details." >> ${RESULTS_DIR}/09-report.res
fi

BUILD_LOG_RES="ERROR"
if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors when building"
    echo 'COMPILATION_RESULTS;ERROR,Compilation log,See Log,build.log' >> ${RESULTS_DIR}/build.txt
    RUN_TESTS=false
    ALL_OK=false
    BUILD_OK=false
else
    echo "the build had no errors!!"
    echo 'COMPILATION_RESULTS;OK,Compilation log,See Log,build.log' >> ${RESULTS_DIR}/build.txt
    if [ ! -e $WORKSPACE/new-build-warnings.log ] ; then
      BUILD_LOG_RES="OK"
    elif [ ! -d ${BUILD_LOG_DIR}/src ] ; then
      BUILD_LOG_RES="OK"
    fi
    #Check Build Rule: Make sure nothing rebuilds after last build
    if [ $(cat $WORKSPACE/$CMSSW_IB/config/config_tag  | sed 's|V||;s|-||g;s|^0*||') -gt 50807 ] ; then
        scram build -f -j ${NCPU} -d  >${WORKSPACE}/scram-rebuild.log 2>&1
        grep ' newer ' ${WORKSPACE}/scram-rebuild.log | grep -v '/cache/xlibs.backup' > ${WORKSPACE}/newer-than-target.log || true
        if [ -s ${WORKSPACE}/newer-than-target.log ] ; then
            echo "SCRAM_REBUILD;ERROR,Build Rules,See Log,newer-than-target.log" >> ${RESULTS_DIR}/build.txt
        fi
    fi
    #Check for missing Provides
    if ${CMS_BOT_DIR}/pr_testing/test-cmssw-provides.sh ${PKG_TOOL_BRANCH} ${CMSDIST_TAG} ${BUILD_DIR} ${WEEK_NUM} >$WORKSPACE/rpm-deps-checks.log 2>&1 ; then
      echo "SCRAM_RPM_DEPS;OK,Package dependency,See Log,rpm-deps-checks.log" >> ${RESULTS_DIR}/build.txt
    else
      echo "SCRAM_RPM_DEPS;ERROR,Package dependency,See Log,rpm-deps-checks.log" >> ${RESULTS_DIR}/build.txt
    fi
fi
echo "BUILD_LOG;${BUILD_LOG_RES},Compilation warnings summary,See Logs,build-logs" >> ${RESULTS_DIR}/build.txt

# Analyze LLVM compilation logs
if [ -f $WORKSPACE/buildClang.log ] ; then
  get_compilation_warnings $WORKSPACE/buildClang.log > $WORKSPACE/all-warnings-clang.log
  for i in $(get_warnings_files $WORKSPACE/all-warnings-clang.log $WORKSPACE/full-list-of-changed-files.txt) ; do
    echo $i >> $WORKSPACE/clang-new-warnings.log
    grep ": warning: " $WORKSPACE/all-warnings-clang.log | grep "/$i" >> $WORKSPACE/clang-new-warnings.log
  done
  if [ -e $WORKSPACE/clang-new-warnings.log ]  ; then
    echo 'CLANG_NEW_WARNINGS;ERROR,Clang Warnings to fix,See Log,clang-new-warnings.log' >> ${RESULTS_DIR}/clang.txt
    if $IS_DEV_BRANCH && [ $(echo "$IGNORE_BOT_TESTS" | tr ',' '\n' | grep '^CLANG-WARNINGS$' | wc -l) -eq 0 ] ; then
      RUN_TESTS=false
      ALL_OK=false
      CLANG_BUILD_OK=false
    fi
  fi
fi

[ "$BUILD_ONLY" = "true" ] && RUN_TESTS=false

DO_PROFILING=false
DO_GPU_TESTS=false
if [ "X$BUILD_OK" = Xtrue -a "$RUN_TESTS" = "true" ]; then
  if [ "X$DO_TESTS" = Xtrue ] ; then
    mark_commit_status_all_prs 'unittest' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  fi
  if [ "X$DO_SHORT_MATRIX" = Xtrue ] ; then
    mark_commit_status_all_prs 'relvals' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  fi
  if [ "X$DO_ADDON_TESTS" = Xtrue ] ; then
    mark_commit_status_all_prs 'addon' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  fi
  if [ "X$DO_CRAB_TESTS" = Xtrue ] ; then
    mark_commit_status_all_prs 'crab' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  fi
  if [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep '^PROFILING$' | wc -l) -gt 0 ] ; then
    if $PRODUCTION_RELEASE ; then
      DO_PROFILING=true
      if [ "X$PROFILING_WORKFLOWS" = "X" ] ; then
        PROFILING_WORKFLOWS=$($CMS_BOT_DIR/cmssw-pr-test-config _PROFILING | tr ',' ' ')
      else
        PROFILING_WORKFLOWS=$(echo $PROFILING_WORKFLOWS | tr ',' ' ')
      fi
      for wf in $PROFILING_WORKFLOWS;do
        mark_commit_status_all_prs "profiling wf $wf" 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
      done
    fi
  fi
  if [ ${#SELECTED_GPU_TYPES[@]} -ne 0 -a X"${DISABLE_GPU_TESTS}" != X"true" ] ; then
    DO_GPU_TESTS=true
  fi
  if [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep '^HLT_P2_TIMING$' | wc -l) -gt 0 ] ; then
    if [ $(echo ${ARCHITECTURE}   | grep "_amd64_" | wc -l) -gt 0 ] ; then
      if [ -e ${CMSSW_RELEASE_BASE}/src/HLTrigger/Configuration/python/HLT_75e33/test/runHLTTiming.sh ]; then
        DO_HLT_P2_TIMING=true
        mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
      fi
    fi
  fi
  if [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep '^HLT_P2_INTEGRATION$' | wc -l) -gt 0 ] ; then
    if [ $(echo ${ARCHITECTURE}   | grep "_amd64_" | wc -l) -gt 0 ] ; then
      if [ -e ${CMSSW_RELEASE_BASE}/src/HLTrigger/Configuration/scripts/hltPhase2UpgradeIntegrationTests ]; then
        DO_HLT_P2_INTEGRATION=true
        mark_commit_status_all_prs 'hlt-p2-integration' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
      fi
    fi
  fi
else
  DO_TESTS=false
  DO_SHORT_MATRIX=false
  DO_ADDON_TESTS=false
  DO_CRAB_TESTS=false
  DO_HLT_P2_TIMING=false
  DO_HLT_P2_INTEGRATION=false
fi

REPORT_OPTS="--report-url ${PR_RESULT_URL} $NO_POST"
rm -f ${RESULTS_DIR}/10-report.res ; touch ${RESULTS_DIR}/10-report.res
if ${ALL_OK} ; then
    if [ "${BUILD_LOG_RES}" = "ERROR" ] ; then
      echo "Found compilation warnings" >> ${RESULTS_DIR}/10-report.res
    fi
    REPORT_STATUS="success"
    REPORT_TEXT="Passed"
else
   TESTS_FAILED=""
   if [ "X$BUILD_OK" = Xfalse ] ;         then TESTS_FAILED="$TESTS_FAILED  Build" ; fi
   if [ "X$CHK_HEADER_OK" = Xfalse ] ;    then TESTS_FAILED="$TESTS_FAILED  HeaderConsistency" ; fi
   if [ "X$CLANG_BUILD_OK" = Xfalse ];    then TESTS_FAILED="$TESTS_FAILED  ClangBuild" ; fi
    if [ "X$PYTHON3_BUILD_OK" = Xfalse ]; then TESTS_FAILED="$TESTS_FAILED  Python3" ; fi
    REPORT_GEN_OPTS="--repo cms-sw/cmssw --report-file ${RESULTS_DIR}/10-report.res ${REPORT_OPTS} "
    echo "${TESTS_FAILED}" > ${RESULTS_DIR}/10-failed.res
    if [ "X$BUILD_OK" = Xfalse ]; then
      $CMS_BOT_DIR/report-pull-request-results PARSE_BUILD_FAIL -f $WORKSPACE/build.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$CLANG_BUILD_OK" = Xfalse ]; then
      $CMS_BOT_DIR/report-pull-request-results PARSE_CLANG_BUILD_FAIL -f $WORKSPACE/buildClang.log ${REPORT_GEN_OPTS}
    fi
    if [ "X$PYTHON3_BUILD_OK" = Xfalse ]; then
      $CMS_BOT_DIR/report-pull-request-results PYTHON3_FAIL -f $WORKSPACE/python3.log ${REPORT_GEN_OPTS}
    fi
    REPORT_STATUS="error"
    REPORT_TEXT="Failed: ${TESTS_FAILED}"
fi
if [ -e ${RESULTS_DIR}/static.txt ]; then
  if [ $(grep ${RESULTS_DIR}/static.txt -e 'EDM_ML_DEBUG_CHECKS;OK' | wc -l) -eq 0 ]; then
    echo "* Static analyzer reported errors, please check" >> ${RESULTS_DIR}/10-report.res
  fi 
fi
$CMS_BOT_DIR/das-utils/use-ibeos-sort || true

pushd $WORKSPACE
  rm -rf ${CMSSW_IB}/das_query
  backup_dirs="tmp llvm-analysis"
  for d in $backup_dirs ; do if [ -e ${CMSSW_IB}/${d} ] ; then mv ${CMSSW_IB}/${d} ${CMSSW_IB}.${d} ; fi ; done
  tar -czf cmssw.tar.gz $CMSSW_IB
  for d in $backup_dirs ; do if [ -e ${CMSSW_IB}.${d} ] ; then mv ${CMSSW_IB}.${d} ${CMSSW_IB}/${d} ; fi ; done
popd

prepare_upload_results
mark_commit_status_all_prs '' $REPORT_STATUS -u "${PR_RESULT_URL}" -d "${REPORT_TEXT}"
rm -rf $WORKSPACE/upload

echo "PR_BUILD_BASE=${WORKSPACE}" > $WORKSPACE/deploy-cmssw
echo "CMS_WEEK=${CMS_WEEKLY_REPO}" >> $WORKSPACE/deploy-cmssw
echo "PR_REPOSITORY=${PR_EXTERNAL_REPO}" >> $WORKSPACE/deploy-cmssw
echo "ARCHITECTURE=${ARCHITECTURE}" >> $WORKSPACE/deploy-cmssw
echo "PR_TEST_BUILD_ID=${BUILD_NUMBER}" >> $WORKSPACE/deploy-cmssw
echo "PULL_REQUEST=${PULL_REQUEST}" >> $WORKSPACE/deploy-cmssw
echo "PULL_REQUESTS=${PULL_REQUESTS}" >> $WORKSPACE/deploy-cmssw
echo "RELEASE_FORMAT=$CMSSW_IB" >> $WORKSPACE/deploy-cmssw

if [ "${BUILD_ONLY}" = "true" ]; then
  if ${ALL_OK} ; then
    echo "+1" > comment.txt
  else
    echo "-1" > comment.txt
  fi
  echo "" >> comment.txt
  curl -L ${PR_COMMENT_TEXT_URL} >> comment.txt
  $WORKSPACE/cms-bot/comment-gh-pr.py --repository ${PR_REPO} --pullrequest ${PR_NUMBER} --report-file comment.txt
  mark_commit_status_all_prs "${PR_COMMIT_STATUS}" 'success' -u "${BUILD_URL}" -d "Finished" -e
fi

if [ "X$BUILD_OK" != Xtrue -o "$RUN_TESTS" != "true" ]; then exit 0 ; fi

touch $WORKSPACE/job.env
for x in REPORT_OPTS BUILD_EXTERNAL DO_DUPLICATE_CHECKS DO_DAS_QUERY DO_TESTS CMSDIST_ONLY CMSSW_IB UPLOAD_UNIQ_ID PRODUCTION_RELEASE; do
  eval echo "$x=\\\"$(echo \$$x)\\\"" >> $WORKSPACE/job.env
done


echo "UPLOAD_UNIQ_ID=${UPLOAD_UNIQ_ID}" > $WORKSPACE/test-env.txt
echo "CMSSW_CVMFS_PATH=/cvmfs/cms-ci.cern.ch/week${WEEK_NUM}/${PR_REPO}/${PR_NUMBER}/${BUILD_NUMBER}/${CMSSW_VERSION}" >> $WORKSPACE/test-env.txt
echo "PULL_REQUEST=${PULL_REQUEST}" >> $WORKSPACE/test-env.txt
echo "PULL_REQUESTS=${PULL_REQUESTS}" >> $WORKSPACE/test-env.txt
echo "ARCHITECTURE=${ARCHITECTURE}" >> $WORKSPACE/test-env.txt
echo "RELEASE_FORMAT=${RELEASE_FORMAT}" >> $WORKSPACE/test-env.txt
echo "RUN_ON_SLAVE=${RUN_ON_SLAVE}" >> $WORKSPACE/test-env.txt
echo "DOCKER_IMG=${DOCKER_IMG}" >> $WORKSPACE/test-env.txt
echo "CONFIG_LINE=${CONFIG_LINE}" >> $WORKSPACE/test-env.txt
echo "AUTO_POST_MESSAGE=${AUTO_POST_MESSAGE}" >> $WORKSPACE/test-env.txt
echo "CONTEXT_PREFIX=${CONTEXT_PREFIX}" >> $WORKSPACE/test-env.txt
echo "PRODUCTION_RELEASE=${PRODUCTION_RELEASE}" >> $WORKSPACE/test-env.txt

# Store externals path for CRAB unit test
if [ "X$DO_CRAB_TESTS" = Xtrue ]; then
    cp $WORKSPACE/test-env.txt $WORKSPACE/run-crab.prop
    echo "PR_CVMFS_PATH=/cvmfs/cms-ci.cern.ch/week${WEEK_NUM}/${PR_EXTERNAL_REPO}" >> $WORKSPACE/run-crab.prop
    echo "RELEASE_FORMAT=${CMSSW_IB}" >> $WORKSPACE/run-crab.prop
    echo "PR_RESULT_URL=${PR_RESULT_URL}" >> $WORKSPACE/run-crab.prop
    echo "LAST_PR_COMMIT=${LAST_PR_COMMIT}" >> $WORKSPACE/run-crab.prop
    echo "CMSSW_QUEUE=${CMSSW_QUEUE}" >> $WORKSPACE/run-crab.prop
    echo "UPLOAD_UNIQ_ID=${UPLOAD_UNIQ_ID}" >> $WORKSPACE/run-crab.prop
fi

#
# Matrix tests
if [ "X$DO_SHORT_MATRIX" = Xtrue ]; then
  cp $WORKSPACE/test-env.txt $WORKSPACE/run-relvals.prop
  echo "DO_COMPARISON=$DO_COMPARISON" >> $WORKSPACE/run-relvals.prop
  echo "MATRIX_TIMEOUT=$MATRIX_TIMEOUT" >> $WORKSPACE/run-relvals.prop
  echo "COMPARISON_REL=${COMPARISON_REL}" >> $WORKSPACE/run-relvals.prop
  echo "COMPARISON_ARCH=${COMPARISON_ARCH}" >> $WORKSPACE/run-relvals.prop
  echo "REAL_ARCH=${RELVAL_REAL_ARCH}" >> $WORKSPACE/run-relvals.prop
  WF_COMMON="-s $(get_pr_relval_args $DO_COMPARISON '')"
  [ "${WORKFLOWS_PR_LABELS}" != "" ] && WF_COMMON="${WF_COMMON};-l ${WORKFLOWS_PR_LABELS}"
  echo "MATRIX_ARGS=${WF_COMMON}" >> $WORKSPACE/run-relvals.prop
  FULL_MATRIX_ARGS="${EXTRA_MATRIX_COMMAND_ARGS}"
  if  $ENABLE_MEMORY_PROFILE ; then
    if cmsDriver.py --help | grep -q '\-\-maxmem_profile' ; then
      FULL_MATRIX_ARGS="--maxmem_profile ${FULL_MATRIX_ARGS}"
    else
      ENABLE_MEMORY_PROFILE=false
    fi
  fi
  if [ "${FULL_MATRIX_ARGS}" != "" ] ; then
    echo "RUN_THE_MATRIX_CMD_OPTS=${FULL_MATRIX_ARGS}" >> $WORKSPACE/run-relvals.prop
  fi

  for tn in threading rntuple ; do
    uc_tn=$(echo $tn | tr a-z A-Z)
    if [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep "^${uc_tn}$" | wc -l) -gt 0 ] ; then
      prop_file="$WORKSPACE/run-relvals-${tn}.prop"
      cp $WORKSPACE/test-env.txt ${prop_file}
      if [ "${tn}" == "rntuple" ] ; then
        echo "DO_COMPARISON=$DO_COMPARISON" >> ${prop_file}
        echo "COMPARISON_REL=${COMPARISON_REL}" >> ${prop_file}
        echo "COMPARISON_ARCH=${COMPARISON_ARCH}" >> ${prop_file}
        echo "REAL_ARCH=${RELVAL_REAL_ARCH}" >> ${prop_file}
      else
        echo "DO_COMPARISON=false" >> ${prop_file}
      fi
      echo "MATRIX_TIMEOUT=$MATRIX_TIMEOUT" >> ${prop_file}
      WF1=$(echo "${WF_COMMON}" | sed 's|;.*||')
      WF2="$(get_pr_relval_args $DO_COMPARISON _${uc_tn} | sed 's|.*;||')"
      [ "${WORKFLOWS_PR_LABELS}" != "" ] && WF2="${WF2};-l ${WORKFLOWS_PR_LABELS}"
      WF2=$(echo "${WF2}" | sed 's|^;*||')
      if [ "${WF2}" != "" ] ; then WF1="${WF1};${WF2}"; fi
      echo "MATRIX_ARGS=${WF1}" >> ${prop_file}
    fi
  done
  if $PRODUCTION_RELEASE ; then
    for ex_type in ${EXTRA_RELVALS_TESTS} ; do
      [ $(echo ${ENABLE_BOT_TESTS} | tr ',' ' ' | tr ' ' '\n' | grep "^${ex_type}$" | wc -l) -gt 0 ] || continue
      WF_LIST=$(get_pr_baseline_worklflow "_${ex_type}")
      [ "$WF_LIST" != "" ] || continue
      ex_type_lc=$(echo ${ex_type} | tr '[A-Z]' '[a-z]')
      grep -v '^MATRIX_ARGS=' $WORKSPACE/run-relvals.prop > $WORKSPACE/run-relvals-${ex_type_lc}.prop
      echo "MATRIX_ARGS=$(get_pr_relval_args $DO_COMPARISON _${ex_type})" >> $WORKSPACE/run-relvals-${ex_type_lc}.prop
      if [ "${ENABLE_MEMORY_PROFILE}" = "true" -a "${ex_type}" = "ROCM" ] ; then
        sed -i -e 's|RUN_THE_MATRIX_CMD_OPTS=\-\-maxmem_profile\s*|RUN_THE_MATRIX_CMD_OPTS=|' $WORKSPACE/run-relvals-${ex_type_lc}.prop
      fi
    done
    if [ $(runTheMatrix.py --help | grep '^ *--maxSteps' | wc -l) -eq 0 ] ; then
      mark_commit_status_all_prs "relvals/input" 'success' -u "${BUILD_URL}" -d "Not ran, runTheMatrix does not support --maxSteps flag" -e
      TEST_RELVALS_INPUT=false
    fi
    if $TEST_RELVALS_INPUT ; then
      runTheMatrix.py -n -e | grep '\[1\]:' > $WORKSPACE/${CMSSW_IB}/wfs.step1
      WF_LIST=$(cat $WORKSPACE/${CMSSW_IB}/wfs.step1 | grep '\[1\]:  *input from' | sed 's| .*||' |tr '\n' ',' | sed 's|,*$||')
      cp $WORKSPACE/test-env.txt $WORKSPACE/run-relvals-input.prop
      echo "MATRIX_TIMEOUT=$MATRIX_TIMEOUT" >> $WORKSPACE/run-relvals-input.prop
      echo "MATRIX_ARGS=-l ${WF_LIST}"      >> $WORKSPACE/run-relvals-input.prop
      echo "DO_COMPARISON=false"            >> $WORKSPACE/run-relvals-input.prop
    fi
  fi
  for rtype in $(ls $WORKSPACE/run-relvals-*.prop 2>/dev/null | sed 's|.*/run-relvals-||;s|.prop$||') ; do
    echo "TEST_FLAVOR=${rtype}" >> $WORKSPACE/run-relvals-${rtype}.prop
    mark_commit_status_all_prs "relvals/${rtype}" 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  done
fi

if $TEST_DASGOCLIENT && $PRODUCTION_RELEASE ; then
  cp $WORKSPACE/test-env.txt $WORKSPACE/run-dasgoclient.prop
  echo "NEW_DASGOCLIENT_DIR=/cvmfs/cms-ci.cern.ch/week${WEEK_NUM}/${PR_EXTERNAL_REPO}/${ARCHITECTURE}" >> $WORKSPACE/run-dasgoclient.prop
  echo "OLD_DASGOCLIENT_DIR=/cvmfs/cms-ib.cern.ch/week${WEEK_NUM}" >> $WORKSPACE/run-dasgoclient.prop
fi

if [ "X$DO_ADDON_TESTS" = Xtrue ]; then
  cp $WORKSPACE/test-env.txt $WORKSPACE/run-addon.prop
fi

if [ "X$DO_GPU_TESTS" = Xtrue ]; then
  for GPU_T in ${SELECTED_GPU_TYPES[@]}; do
    GPU_T_LC=$(echo $GPU_T | tr '[A-Z]' '[a-z]')
    cp $WORKSPACE/test-env.txt $WORKSPACE/run-unittests-${GPU_T_LC}.prop
    echo "TEST_FLAVOR=${GPU_T_LC}" >> $WORKSPACE/run-unittests-${GPU_T_LC}.prop
    mark_commit_status_all_prs "unittests/${GPU_T_LC}" 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  done
fi

if ${BUILD_EXTERNAL} ; then
  if [ "$(echo ${CMSSW_DEVEL_BRANCH} | cut -d_ -f-3)" = "$(echo ${CMSSW_DEVEL_BRANCH} | cut -d_ -f-3)" ] ; then
    cp $WORKSPACE/test-env.txt $WORKSPACE/run-external_checks.prop
  fi
fi

if [ "${DO_PROFILING}" = "true" ]  ; then
  if [ "X$PROFILING_WORKFLOWS" = "X" ] ; then
    PROFILING_WORKFLOWS=$($CMS_BOT_DIR/cmssw-pr-test-config _PROFILING | tr ',' ' ')
  else
    PROFILING_WORKFLOWS=$(echo ${PROFILING_WORKFLOWS} | tr ',' ' ')
  fi
  for wf in ${PROFILING_WORKFLOWS}; do
    cp $WORKSPACE/test-env.txt $WORKSPACE/run-profiling-$wf.prop
    echo "PROFILING_WORKFLOWS=${wf}" >> $WORKSPACE/run-profiling-$wf.prop
  done
fi

if [ "${DO_HLT_P2_TIMING}" = "true" ] ;  then
  cp $WORKSPACE/test-env.txt $WORKSPACE/run-hlt_p2_timing.prop
fi

if [ "${DO_HLT_P2_INTEGRATION}" = "true" ] ;  then
  cp $WORKSPACE/test-env.txt $WORKSPACE/run-hlt_p2_integration.prop
fi

rm -f $WORKSPACE/test-env.txt

