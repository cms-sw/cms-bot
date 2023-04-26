#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

mark_commit_status_all_prs 'gpu' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
echo '--------------------------------------'
GPU_CMD="LOCALRT=${WORKSPACE}/${CMSSW_VERSION} USER_UNIT_TESTS=cuda timeout 7200 scram b runtests -j ${NCPU}"
echo $GPU_CMD > $WORKSPACE/gpuUnitTests.log
STIME=$(date +%s)
(eval $GPU_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/gpuUnitTests.log
set DTIME=$(date +%s)-$STIME
echo 'END OF GPU UNIT TESTS'
echo '--------------------------------------'
if [ $(grep -a ' tests passed, ' $WORKSPACE/gpuUnitTests.log | wc -l) -eq 0 ] ; then
  echo "GpuUnitTest might have timed out: FAILED - $DTIME secs" >>  $WORKSPACE/gpuUnitTests.log
fi

TEST_ERRORS=`grep -ai -E ": FAILED .*" $WORKSPACE/gpuUnitTests.log` || true
GENERAL_ERRORS=`grep -a "ALL_OK" $WORKSPACE/gpuUnitTests.log` || true

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the gpuUnitTests"
  echo 'GPU_TESTS;ERROR,GPU Unit Tests,See Logs,gpuUnitTests' >> ${RESULTS_DIR}/gpu.txt
  ALL_OK=false
  GPU_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_GPU_FAIL -f $WORKSPACE/gpuUnitTests.log --report-file ${RESULTS_DIR}/14-gpu-report.res --report-url ${PR_RESULT_URL}
  echo "GPU" > ${RESULTS_DIR}/14-gpu-failed.res
else
  touch ${RESULTS_DIR}/14-gpu-failed.res
  touch ${RESULTS_DIR}/14-gpu-report.res
  echo "no errors in the gpuUnitTests!!"
  echo 'GPU_TESTS;OK,GPU Unit Tests,See Logs,gpuUnitTests' >> ${RESULTS_DIR}/gpu.txt
fi
prepare_upload_results
if $GPU_OK ; then
  mark_commit_status_all_prs 'gpu' 'success' -u "${BUILD_URL}" -d "Passed"
else
  mark_commit_status_all_prs 'gpu' 'error' -u "${BUILD_URL}" -d "Errors in the gpuUnitTests"
fi
