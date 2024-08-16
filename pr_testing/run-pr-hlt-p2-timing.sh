#!/bin/bash -ex
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | sed 's|^.*/||;s|#||')
UPLOAD_PATH="${CMSSW_VERSION}-${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
HLT_P2_SCRIPT="src/HLTrigger/Configuration/python/HLT_75e33/test"
HLT_BASEDIR="${CMSSW_BASE}"
if [ ! -e "${HLT_BASEDIR}/${HLT_P2_SCRIPT}" ] ; then HLT_BASEDIR="${CMSSW_RELEASE_BASE}" ; fi
mkdir -p ${RESULTS_DIR} $WORKSPACE/json_upload $WORKSPACE/rundir
cp -r ${HLT_BASEDIR}/${HLT_P2_SCRIPT}/* $WORKSPACE/rundir/

pushd $WORKSPACE/rundir
  export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
  timeout $TIMEOUT ${HLT_BASEDIR}/${HLT_P2_SCRIPT}/runHLTTiming.sh >${RESULTS_DIR}/hlt-p2-timing.log 2>&1 | tee ${RESULTS_DIR}/hlt-p2-timing.log
popd

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
touch ${RESULTS_DIR}/15-hlt-p2-timing-report.res ${RESULTS_DIR}/15-hlt-p2-timing-failed.res
if [ -f $WORKSPACE/rundir/Phase2Timing_resources.json ] ; then
  CHART_URL="https://cmssdt.cern.ch/circles/web/piechart.php?data_name=hlt-p2-timing&resource=time_thread&filter=${CMSSW_VERSION}&dataset=${UPLOAD_PATH}/Phase2Timing_resources"
  echo "HLT_P2_TIMING;SUCCESS,HLT Phase 2 timing Test,See Chart,${CHART_URL}" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo -e "\n* **HLT P2 Timing**: [chart](${CHART_URL})" > ${RESULTS_DIR}/15-hlt-p2-timing-report.res

  mv $WORKSPACE/rundir/Phase2Timing*.json $WORKSPACE/json_upload
  send_jenkins_artifacts $WORKSPACE/json_upload hlt-p2-timing/${UPLOAD_PATH}
  mark_commit_status_all_prs 'hlt-p2-timing' 'success' -u "${BUILD_URL}" -d "HLT Phase2 timing data collected"
else
  echo "HLT_P2_TIMING;ERROR,HLT Phase 2 timing Test,See Logs,hlt-p2-timing.log" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo "HLTP2Timing" > ${RESULTS_DIR}/15-hlt-p2-timing-failed.res
  mark_commit_status_all_prs 'hlt-p2-timing' 'error' -u "${BUILD_URL}" -d "HLT Phase2 timing script failed"
fi
rm -rf $WORKSPACE/json_upload $WORKSPACE/rundir
prepare_upload_results
