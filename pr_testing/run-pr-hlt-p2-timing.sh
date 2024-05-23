#!/bin/bash -ex
echo "FAILED" > $WORKSPACE/testsResults/statusfile-hlt-p2-timing.log

[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | cut -d '/' -f 2 | cut -d '#' -f 1)
UPLOAD_PATH="${RELEASE_FORMAT}+${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
timeout $TIMEOUT ${CMSSW_CVMFS_PATH}/src/HLTrigger/Configuration/python/HLT_75e33/test/runHLTTiming.sh 2>&1 | tee $WORKSPACE/hlt-p2-timing.log
CHART_URL="/circles/web/piechart.php?data_name=hlt-p2-timing&resource=time_thread&filter=${UPLOAD_PATH}&dataset=${UPLOAD_PATH}/Phase2Timing_resources"

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
if [ -f $WORKSPACE/Phase2Timing_resources.json ] ; then
  echo "HLT_P2_TIMING;SUCCESS,HLT Phase 2 timing Test,See Chart,${CHART_URL}" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  touch ${RESULTS_DIR}/hlt-p2-timing-failed.res
  echo "HLT P2 timing: [chart](${CHART_URL})" > ${RESULTS_DIR}/hlt-p2-timing-report.res

  mv WORKSPACE/Phase2Timing_resources*.json $WORKSPACE/testsResults
  send_jenkins_artifacts $WORKSPACE/testsResults hlt-p2-timing/${UPLOAD_PATH}
  mark_commit_status_all_prs 'hlt-p2-timing' 'success' -u "${BUILD_URL}" -d "HLT Phase2 timing data collected"
else
  echo "HLT_P2_TIMING;ERROR,HLT Phase 2 timing Test,See Logs,hlt-p2-timing.log" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo "HLT_P2_TIMING" > ${RESULTS_DIR}/hlt-p2-timing-failed.res

  mark_commit_status_all_prs 'hlt-p2-timing' 'error' -u "${BUILD_URL}" -d "HLT Phase2 timing script failed"
fi

prepare_upload_results

