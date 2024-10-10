SCRIPTPATH="$( cd "$(dirname "$0")" ; /bin/pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
COMMON=${CMS_BOT_DIR}/common
if [ "$WORKSPACE" = "" ] ; then export WORKSPACE=$(/bin/pwd -P) ; fi
source ${CMS_BOT_DIR}/cmsrep.sh
source ${PR_TESTING_DIR}/_helper_functions.sh
source ${CMS_BOT_DIR}/jenkins-artifacts
source ${COMMON}/github_reports.sh
if [ "$(systemctl is-system-running 2>/dev/null || true)" = "offline" ] ; then
  if [ "${DBUS_SESSION_BUS_ADDRESS}" != "" ] ; then
    unset DBUS_SESSION_BUS_ADDRESS
  fi
fi
NCPU=$(${COMMON}/get_cpu_number.sh)
if [ "${DRY_RUN}" = "false" ] ; then AUTO_POST_MESSAGE="true"; fi
NO_POST=''
DRY_RUN=''
if [ "X$AUTO_POST_MESSAGE" != Xtrue ]; then
  NO_POST='--no-post'
  DRY_RUN='--dry-run'
fi

export LC_ALL=C
JENKINS_PREFIX=$(echo "${JENKINS_URL}" | sed 's|/*$||;s|.*/||')
if [ "X${JENKINS_PREFIX}" = "X" ] ; then JENKINS_PREFIX="jenkins"; fi
export JENKINS_PREFIX
if [ -e $WORKSPACE/job.env ] ; then source $WORKSPACE/job.env ; fi
if [ "${DRY_RUN}" = "" ] ; then
  PR_RESULT_URL="https://cmssdt.cern.ch/SDT/${JENKINS_PREFIX}-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}"
  if [ ! -f $WORKSPACE/prs_commits ] ; then
    get_jenkins_artifacts pull-request-integration/${UPLOAD_UNIQ_ID}/prs_commits.txt $WORKSPACE/prs_commits
  fi
fi
cp -f $CMS_BOT_DIR/das-utils/das_client $CMS_BOT_DIR/das-utils/das_client.py
if [ -e $WORKSPACE/$BUILD_DIR/cmsset_default.sh ] ; then
  source $WORKSPACE/$BUILD_DIR/cmsset_default.sh
elif ! which scram >/dev/null 2>&1 ; then
  source /cvmfs/cms.cern.ch/cmsset_default.sh
fi
which dasgoclient
export CMS_PATH=/cvmfs/cms-ib.cern.ch
if [ "X$CMS_SITE_OVERRIDE" == "X" ]; then
  CMS_SITE_OVERRIDE="local"
fi
export SITECONFIG_PATH=/cvmfs/cms-ib.cern.ch/SITECONF/$CMS_SITE_OVERRIDE
mkdir -p ${RESULTS_DIR}
[ "${ARCHITECTURE}" != "" ] && export SCRAM_ARCH=${ARCHITECTURE}
export SCRAM_PREFIX_PATH=${CMS_BOT_DIR}/das-utils
case $CMSSW_IB in
  *ASAN* )
   $CMS_BOT_DIR/system-overrides.sh $WORKSPACE/system-overrides
   export SCRAM_PREFIX_PATH=$WORKSPACE/system-overrides:${SCRAM_PREFIX_PATH}
   ;;
esac
if [ "${CMSSW_CVMFS_PATH}" != "" ] ; then
  WAIT_TIME=14400
  while [ $WAIT_TIME -gt 0 ] ; do
    if [ -d ${CMSSW_CVMFS_PATH} ] ; then
      break
    fi
    sleep 60
    let WAIT_TIME=${WAIT_TIME}-60 || true
  done
  pushd ${CMSSW_CVMFS_PATH}
    eval `scram run -sh` >/dev/null 2>&1
  popd
  mkdir -p $WORKSPACE/${CMSSW_VERSION}
  if [ -f ${CMSSW_CVMFS_PATH}/ibeos_cache.txt ] ; then ln -s ${CMSSW_CVMFS_PATH}/ibeos_cache.txt $WORKSPACE/${CMSSW_VERSION}/ibeos_cache.txt ; fi
  ln -s ${CMSSW_CVMFS_PATH}/src $WORKSPACE/${CMSSW_VERSION}/src
else
  pushd $WORKSPACE/$CMSSW_IB
    eval `scram run -sh` >/dev/null 2>&1
  popd
fi
export PATH=$CMS_BOT_DIR/das-utils:$PATH
which dasgoclient
which ibeos-lfn-sort
CMSSW_IB=${CMSSW_VERSION}
CMSSW_QUEUE=$(echo ${CMSSW_VERSION} | sed 's|_X.*|_X|')
if [ "${UPLOAD_UNIQ_ID}" != "" ] ; then
  PR_TEST_BUILD_NUMBER=$(echo ${UPLOAD_UNIQ_ID} | sed 's|.*/||')
fi
