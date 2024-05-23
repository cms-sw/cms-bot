#!/bin/bash -ex
echo "FAILED" > $WORKSPACE/testsResults/statusfile-hlt-p2-timing.log

[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | sed 's|^.*/||;s|#||')
UPLOAD_PATH="${CMSSW_VERSION}+${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
HLT_P2_SCRIPT="src/HLTrigger/Configuration/python/HLT_75e33/test/runHLTTiming.sh"
if [ -e ${CMSSW_BASE}/${HLT_P2_SCRIPT} ] ; then
  HLT_P2_SCRIPT="${CMSSW_BASE}/${HLT_P2_SCRIPT}"
else
  HLT_P2_SCRIPT="${CMSSW_RELEASE_BASE}/${HLT_P2_SCRIPT}"
fi
export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
timeout $TIMEOUT ${HLT_P2_SCRIPT} 2>&1 | tee $WORKSPACE/hlt-p2-timing.log
CHART_URL="https://cmssdt.cern.ch/circles/web/piechart.php?data_name=hlt-p2-timing&resource=time_thread&filter=${CMSSW_VERSION}&dataset=${UPLOAD_PATH}/Phase2Timing_resources"

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
if [ -f $WORKSPACE/Phase2Timing_resources.json ] ; then
  echo "HLT_P2_TIMING;SUCCESS,HLT Phase 2 timing Test,See Chart,${CHART_URL}" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  touch ${RESULTS_DIR}/15-hlt-p2-timing-failed.res
  echo "HLT P2 timing: [chart](${CHART_URL})" > ${RESULTS_DIR}/15-hlt-p2-timing-report.res

  mv $WORKSPACE/Phase2Timing_resources*.json $WORKSPACE/testsResults
  send_jenkins_artifacts $WORKSPACE/testsResults hlt-p2-timing/${UPLOAD_PATH}
  mark_commit_status_all_prs 'hlt-p2-timing' 'success' -u "${BUILD_URL}" -d "HLT Phase2 timing data collected"
else
  echo "HLT_P2_TIMING;ERROR,HLT Phase 2 timing Test,See Logs,hlt-p2-timing.log" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo "HLTP2Timing" > ${RESULTS_DIR}/15-hlt-p2-timing-failed.res

  mark_commit_status_all_prs 'hlt-p2-timing' 'error' -u "${BUILD_URL}" -d "HLT Phase2 timing script failed"
fi

prepare_upload_results

