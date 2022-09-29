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
LOG=$WORKSPACE/matrixTests${UC_TEST_FLAVOR}.log
touch ${LOG}
echo "${MATRIX_ARGS}"  | tr ';' '\n' | while IFS= read -r args; do
  dateBefore=$(date +"%s")
  (LOCALRT=${WORKSPACE}/${CMSSW_VERSION} CHECK_WORKFLOWS=false UPLOAD_ARTIFACTS=false MATRIX_ARGS="$args" timeout $MATRIX_TIMEOUT ${CMS_BOT_DIR}/run-ib-pr-matrix.sh "${TEST_FLAVOR}" && echo ALL_OK) 2>&1 | tee ${LOG}.tmp
  if [ $(grep -a "ALL_OK" ${LOG}.tmp | wc -l) -eq 0 ] ; then echo "ERROR Running runTheMatrix for '$args'" >> ${LOG}.tmp ; fi
  cat ${LOG}.tmp >> ${LOG}
  rm -rf ${LOG}.tmp
  dateAfter=$(date +"%s")
  diff=$(($dateAfter-$dateBefore))
  if [ "$diff" -ge $MATRIX_TIMEOUT ]; then
    echo "------------"  >> ${LOG}
    echo 'ERROR TIMEOUT' >> ${LOG}
  fi
  if [ ! -d $WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results ] ; then
    mv $WORKSPACE/matrix-results $WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results
  else
    rsync -a $WORKSPACE/matrix-results/ $WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results/
    rm -rf $WORKSPACE/matrix-results
  fi
  pushd $WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results
    rm -f matrixTests.${BUILD_ID}.log
    for x in wf_mapping.${BUILD_ID}.txt runall-report-step123-.${BUILD_ID}.log wf_errors.${BUILD_ID}.txt ; do
      xm=$(echo $x | sed "s|.${BUILD_ID}\.|.|")
      touch $xm
      if [ -f $x ] ; then
        cat $x >> $xm
        rm -f $x
      fi
    done
  popd
done

pushd $WORKSPACE/runTheMatrix${UC_TEST_FLAVOR}-results
  $DO_COMPARISON && WORKFLOW_TO_COMPARE=$(grep -a '^[1-9][0-9]*' ${LOG} | grep ' Step[0-9]' | sed 's|_.*||' | sort | uniq | tr '\n' ',' | sed 's|,$||')

  rm -f lfns.txt ; touch lfns.txt
  for lfn in $(grep -ahR 'Initiating request to open file' --include 'step*.log' | grep '/cms-xrd-global.cern.ch' | sed 's|.*/cms-xrd-global.cern.ch[^/]*//*|/|;s|[?].*||' | sort | uniq) ; do
    echo "${lfn}" >> lfns.txt
  done
  for lfn in $(grep -ahR 'Failed to open file at URL' --include 'step*.log' | grep '/cms-xrd-global.cern.ch' | sed 's|.*/cms-xrd-global.cern.ch[^/]*//*|/|;s|[?].*||' | sort | uniq) ; do
    echo "${lfn}" >> lfns.txt
  done
  CNT=1
  for lfn in $(cat lfns.txt | grep /store/ | sort | uniq) ; do
    echo "LFN=${lfn}" > $WORKSPACE/lfn-to-ibeos-${CNT}.prop
    let CNT=${CNT}+1
  done
popd

TEST_ERRORS=$(grep -ai -E "ERROR .*" ${LOG} | grep -v 'DAS QL ERROR' | grep -v 'ERROR failed to parse X509 proxy') || true
GENERAL_ERRORS=`grep -a "ALL_OK" ${LOG}` || true

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the RelVals"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;ERROR,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/relval${UC_TEST_FLAVOR}.txt
  ALL_OK=false
  RELVALS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_MATRIX_FAIL -f ${LOG} --report-file ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-report.res --report-url ${PR_RESULT_URL} $NO_POST
  if [ "${TEST_FLAVOR}" != "" ] ; then
    sed -i -e "s|## RelVals|## RelVals-${UC_TEST_FLAVOR}|;s|/runTheMatrix-results|/runTheMatrix${UC_TEST_FLAVOR}-results|g" ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-report.res
    echo "RelVals-${UC_TEST_FLAVOR}" > ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-failed.res
  else
    echo "RelVals" > ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-failed.res
  fi
  mark_commit_status_all_prs "${GH_COMP_CONTEXT}" 'success' -d "Not run due to failure in relvals" ${MARK_OPTS}
else
  touch ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-failed.res
  touch ${RESULTS_DIR}/12${UC_TEST_FLAVOR}-relvals-report.res
  echo "no errors in the RelVals!!"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;OK,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/relval${UC_TEST_FLAVOR}.txt

  if $DO_COMPARISON ; then
    echo "COMPARISON${UC_TEST_FLAVOR};QUEUED,Comparison ${UC_TEST_FLAVOR} with the baseline,See results,See results" >> ${RESULTS_DIR}/comparison${UC_TEST_FLAVOR}.txt
    TRIGGER_COMPARISON_FILE=$WORKSPACE/'comparison.properties'
    echo "Creating properties file $TRIGGER_COMPARISON_FILE"
    echo "RELEASE_FORMAT=$COMPARISON_REL" > $TRIGGER_COMPARISON_FILE
    echo "ARCHITECTURE=${SCRAM_ARCH}" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUESTS=${PULL_REQUESTS}" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUEST_JOB_ID=${PR_TEST_BUILD_NUMBER}" >> $TRIGGER_COMPARISON_FILE
    echo "WORKFLOWS_LIST=${WORKFLOW_TO_COMPARE}" >> $TRIGGER_COMPARISON_FILE
    echo "MATRIX_ARGS=${MATRIX_ARGS}" >> $TRIGGER_COMPARISON_FILE
    echo "COMPARISON_ARCH=$COMPARISON_ARCH" >> $TRIGGER_COMPARISON_FILE
    echo "DOCKER_IMG=$DOCKER_IMG" >> $TRIGGER_COMPARISON_FILE
    echo "PULL_REQUEST=${PULL_REQUEST}" >> $TRIGGER_COMPARISON_FILE
    echo "CONTEXT_PREFIX=${CONTEXT_PREFIX}" >> $TRIGGER_COMPARISON_FILE
    echo "TEST_FLAVOR=${TEST_FLAVOR}" >> $TRIGGER_COMPARISON_FILE
    echo "CMSSW_CVMFS_PATH=${CMSSW_CVMFS_PATH}" >> $TRIGGER_COMPARISON_FILE
    echo "UPLOAD_UNIQ_ID=${UPLOAD_UNIQ_ID}" >> $TRIGGER_COMPARISON_FILE
    echo "COMPARISON_RELEASE=$COMPARISON_REL" >> $TRIGGER_COMPARISON_FILE
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
