#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh
GH_CONTEXT="relvals"
GH_COMP_CONTEXT="comparison"
UC_TEST_FLAVOR=$(echo ${TEST_FLAVOR} | tr '[a-z]' '[A-Z]')
MARK_OPTS=""
if [ ${TEST_FLAVOR} != "" ] ; then
  GH_CONTEXT="${GH_CONTEXT}/${TEST_FLAVOR}"
  GH_COMP_CONTEXT="${GH_COMP_CONTEXT}/${TEST_FLAVOR}"
  MARK_OPTS="-e"
fi

mark_commit_status_all_prs "${GH_CONTEXT}" 'pending' -u "${BUILD_URL}" -d "Running tests" || true
mkdir "$WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results"
pushd "$WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results"
  if [ "${TEST_FLAVOR}" = "threading" ] ; then let NCPU=($(nproc)/4)+1 ; fi
  RELVALS_CMD="LOCALRT=${WORKSPACE}/${CMSSW_VERSION} timeout $MATRIX_TIMEOUT runTheMatrix.py -j ${NCPU} $MATRIX_ARGS"
  LOG=$WORKSPACE/matrixTests${UC_TEST_FLAVOR}.log
  echo $RELVALS_CMD > ${LOG}
  dateBefore=$(date +"%s")
  (eval $RELVALS_CMD && echo 'ALL_OK') 2>&1 | tee -a ${LOG}
  dateAfter=$(date +"%s")
  $DO_COMPARISON && WORKFLOW_TO_COMPARE=$(grep '^[1-9][0-9]*' ${LOG} | grep ' Step[0-9]' | sed 's|_.*||' | tr '\n' ',' | sed 's|,$||')

  diff=$(($dateAfter-$dateBefore))
  if [ "$diff" -ge $MATRIX_TIMEOUT ]; then
    echo "------------"  >> ${LOG}
    echo 'ERROR TIMEOUT' >> ${LOG}
  fi
popd

TEST_ERRORS=`grep -i -E "ERROR .*" ${LOG} | grep -v 'DAS QL ERROR'` | grep -v 'ERROR failed to parse X509 proxy' || true
GENERAL_ERRORS=`grep "ALL_OK" ${LOG}` || true

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the RelVals"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;ERROR,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/relval${UC_TEST_FLAVOR}.txt
  ALL_OK=false
  RELVALS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_MATRIX_FAIL -f ${LOG} --report-file ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-report.res --report-url ${PR_RESULT_URL} $NO_POST
  if [ "${TEST_FLAVOR}" != "" ] ; then
    sed -i -e "s|## RelVals|## RelVals-${UC_TEST_FLAVOR}|;s|/runTheMatrix-results|/runTheMatrix${UC_TEST_FLAVOR}-results|g" ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-report.res
    echo "RelVals-${UC_TEST_FLAVOR}" > ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-failed.res
  else
    echo "RelVals" > ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-failed.res
  fi
  mark_commit_status_all_prs "${GH_COMP_CONTEXT}" 'success' -d "Not run due to failure in relvals" ${MARK_OPTS}
else
  echo "no errors in the RelVals!!"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;OK,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/relval${UC_TEST_FLAVOR}.txt

  if $DO_COMPARISON ; then
    REAL_ARCH=-$(cat /proc/cpuinfo | grep vendor_id | head -n 1 | sed "s/.*: //")
    echo "COMPARISON${UC_TEST_FLAVOR};QUEUED,Comparison ${UC_TEST_FLAVOR} with the baseline,See results,See results" >> ${RESULTS_DIR}/comparison${UC_TEST_FLAVOR}.txt
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
    echo "CONTEXT_PREFIX=${CONTEXT_PREFIX}" >> $TRIGGER_COMPARISON_FILE
    echo "TEST_FLAVOR=${TEST_FLAVOR}" >> $TRIGGER_COMPARISON_FILE
    echo "CMSSW_CVMFS_PATH=${CMSSW_CVMFS_PATH}" >> $TRIGGER_COMPARISON_FILE
    echo "UPLOAD_UNIQ_ID=${UPLOAD_UNIQ_ID}" >> $TRIGGER_COMPARISON_FILE
    echo "COMPARISON_RELEASE=$COMPARISON_REL" > $TRIGGER_COMPARISON_FILE
    mark_commit_status_all_prs "${GH_COMP_CONTEXT}" 'pending' -d "Waiting for tests to start"
  else
    mark_commit_status_all_prs "${GH_COMP_CONTEXT}" 'success' -d "Not run: Disabled for this arch/flavor" ${MARK_OPTS}
  fi
fi
prepare_upload_results
if $RELVALS_OK ; then
  mark_commit_status_all_prs "${GH_CONTEXT}" 'success' -u "${BUILD_URL}" -d "Passed"
else
  mark_commit_status_all_prs "${GH_CONTEXT}" 'error' -u "${BUILD_URL}" -d "Errors found while running runTheMatrix"
fi
