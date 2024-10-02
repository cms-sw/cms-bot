#!/bin/bash -ex
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | sed 's|^.*/||;s|#||')
UPLOAD_PATH="${CMSSW_VERSION}-${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-integration' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
HLT_P2_SCRIPT="src/HLTrigger/Configuration/scripts"
HLT_BASEDIR="${CMSSW_BASE}"
if [ ! -e "${HLT_BASEDIR}/${HLT_P2_SCRIPT}" ] ; then HLT_BASEDIR="${CMSSW_RELEASE_BASE}" ; fi
cp -r ${HLT_BASEDIR}/${HLT_P2_SCRIPT} $WORKSPACE/rundir
rm -rf $WORKSPACE/rundir/__pycache__

pushd $WORKSPACE/rundir
  export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
  timeout $TIMEOUT ${HLT_BASEDIR}/${HLT_P2_SCRIPT}/hltPhase2UpgradeIntegrationTests --parallelJobs $(nproc) 2>&1 | tee -a ${WORKSPACE}/hlt-p2-integration.log
popd

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
touch ${RESULTS_DIR}/15-hlt-p2-integration-report.res ${RESULTS_DIR}/15-hlt-p2-integration-failed.res
if [ -f $WORKSPACE/rundir/Phase2Timing_resources.json ] ; then
    echo "HLT_P2_INTEGRATION;SUCCESS,HLT Phase 2 integration Test" >> ${RESULTS_DIR}/hlt-p2-integration.txt
    echo -e "\n* **HLT P2 Integration**" > ${RESULTS_DIR}/15-hlt-p2-integration-report.res
    mark_commit_status_all_prs 'hlt-p2-integration' 'success' -u "${BUILD_URL}" -d "HLT Phase2 integration data collected"
else
  echo "HLT_P2_INTEGRATION;ERROR,HLT Phase 2 integration Test,See Logs,hlt-p2-integration.log" >> ${RESULTS_DIR}/hlt-p2-integration.txt
  echo "HLTP2Integration" > ${RESULTS_DIR}/15-hlt-p2-integration-failed.res
  mark_commit_status_all_prs 'hlt-p2-integration' 'error' -u "${BUILD_URL}" -d "HLT Phase2 integration script failed"
fi
rm -rf $WORKSPACE/json_upload $WORKSPACE/rundir
prepare_upload_results
