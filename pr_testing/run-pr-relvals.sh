#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

mark_commit_status_all_prs 'relvals' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
mkdir "$WORKSPACE/runTheMatrix-results"
pushd "$WORKSPACE/runTheMatrix-results"
  RELVALS_CMD="LOCALRT=${WORKSPACE}/${CMSSW_VERSION} timeout $MATRIX_TIMEOUT runTheMatrix.py $MATRIX_ARGS -j $(${COMMON}/get_cpu_number.sh -2)"
  echo $RELVALS_CMD > $WORKSPACE/matrixTests.log
  dateBefore=$(date +"%s")
  (eval $RELVALS_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/matrixTests.log
  dateAfter=$(date +"%s")
  WORKFLOW_TO_COMPARE=$(grep '^[1-9][0-9]*' $WORKSPACE/matrixTests.log | grep ' Step[0-9]' | sed 's|_.*||' | tr '\n' ',' | sed 's|,$||')

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
  echo 'MATRIX_TESTS;ERROR,Matrix Tests Outputs,See Logs,runTheMatrix-results' >> ${RESULTS_DIR}/relval.txt
  ALL_OK=false
  RELVALS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_MATRIX_FAIL -f $WORKSPACE/matrixTests.log --report-file ${RESULTS_DIR}/12-report.res --report-url ${PR_RESULT_URL} $NO_POST
  echo "RelVals" > ${RESULTS_DIR}/12-failed.res
  mark_commit_status_all_prs 'comparison' 'success' -d "Not run due to failure in relvals"
else
  echo "no errors in the RelVals!!"
  echo 'MATRIX_TESTS;OK,Matrix Tests Outputs,See Logs,runTheMatrix-results' >> ${RESULTS_DIR}/relval.txt

  if $DO_COMPARISON ; then
    REAL_ARCH=-$(cat /proc/cpuinfo | grep vendor_id | head -n 1 | sed "s/.*: //")
    echo 'COMPARISON;QUEUED,Comparison with the baseline,See results,See results' >> ${RESULTS_DIR}/comparison.txt
    TRIGGER_COMPARISON_FILE=$WORKSPACE/'comparison.properties'
    echo "Creating properties file $TRIGGER_COMPARISON_FILE"
    echo "RELEASE_FORMAT=$COMPARISON_REL" > $TRIGGER_COMPARISON_FILE
    echo "ARCHITECTURE=${SCRAM_ARCH}" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUESTS=${PULL_REQUESTS}" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUEST_JOB_ID=${PR_TEST_BUILD_NUMBER}" >> $TRIGGER_COMPARISON_FILE
    echo "REAL_ARCH=${REAL_ARCH}" >> $TRIGGER_COMPARISON_FILE
    echo "WORKFLOWS_LIST=${WORKFLOW_TO_COMPARE}" >> $TRIGGER_COMPARISON_FILE
    echo "COMPARISON_ARCH=$COMPARISON_ARCH" >> $TRIGGER_COMPARISON_FILE
    echo "DOCKER_IMG=$DOCKER_IMG" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUEST=${PULL_REQUEST}" >> $TRIGGER_COMPARISON_FILE
    mark_commit_status_all_prs 'comparison' 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"
  else
    mark_commit_status_all_prs 'comparison' 'success' -d "No run as comparisons test were disabled"
  fi
fi
prepare_upload_results
if $RELVALS_OK ; then
  mark_commit_status_all_prs 'relvals' 'success' -u "${PR_RESULT_URL}/runTheMatrix-results" -d "Passed"
else
  mark_commit_status_all_prs 'relvals' 'error' -u "${PR_RESULT_URL}/runTheMatrix-results" -d "Errors found while running runTheMatrix"
fi
