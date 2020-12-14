SCRIPTPATH="$( cd "$(dirname "$0")" ; /bin/pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
if [ "$WORKSPACE" = "" ] ; then export WORKSPACE=$(/bin/pwd -P) ; fi
source ${CMS_BOT_DIR}/cmsrep.sh
source ${PR_TESTING_DIR}/_helper_functions.sh
source ${CMS_BOT_DIR}/jenkins-artifacts
source ${COMMON}/github_reports.sh
NCPU=$(${COMMON}/get_cpu_number.sh)
NO_POST='--no-post'
DRY_RUN='--dry-run'
if [ "X$AUTO_POST_MESSAGE" != Xtrue ]; then
  NO_POST='--no-post'
  DRY_RUN='--dry-run'
fi

JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
export JENKINS_PREFIX
PR_RESULT_URL="https://cmssdt.cern.ch/SDT/${JENKINS_PREFIX}-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}"
get_jenkins_artifacts pull-request-integration/${UPLOAD_UNIQ_ID}/prs_commits.txt $WORKSPACE/prs_commits.txt
cp -f $CMS_BOT_DIR/das-utils/das_client $CMS_BOT_DIR/das-utils/das_client.py
#export CMS_PATH=/cvmfs/cms-ib.cern.ch
mkdir -p ${RESULTS_DIR}
WAIT_TIME=14400
while [ $WAIT_TIME -gt 0 ] ; do
  if [ -d ${CMSSW_CVMFS_PATH} ] ; then
    break
  fi
  sleep 60
  let WAIT_TIME=${WAIT_TIME}-60 || true
done
pushd ${CMSSW_CVMFS_PATH}
  eval `scram run -sh`
  export PATH=$CMS_BOT_DIR/das-utils:$PATH
popd
mkdir -p $WORKSPACE/${CMSSW_VERSION}
