#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh
readarray -t REQUIRED_GPU_TYPES < <(tr -d '\r' < "${CMS_BOT_DIR}/gpu_flavors.txt")
readarray -t ONDEMAND_GPU_TYPES < <(tr -d '\r' < "${CMS_BOT_DIR}/gpu_flavors_ondemand.txt")
ALL_GPU_TYPES=( ${REQUIRED_GPU_TYPES[@]} ${ONDEMAND_GPU_TYPES[@]} )


GH_CONTEXT="relvals"
GH_COMP_CONTEXT="comparison"
UC_TEST_FLAVOR=$(echo ${TEST_FLAVOR} | tr '[a-z]' '[A-Z]')
MARK_OPTS=""
if [ "${TEST_FLAVOR}" != "" ] ; then
  GH_CONTEXT="${GH_CONTEXT}/${TEST_FLAVOR}"
  GH_COMP_CONTEXT="${GH_COMP_CONTEXT}/${TEST_FLAVOR}"
  MARK_OPTS="-e"
fi

mark_commit_status_all_prs "${GH_CONTEXT}" 'pending' -u "${BUILD_URL}" -d "Running tests" || true
LOG=$WORKSPACE/matrixTests${UC_TEST_FLAVOR}.log
touch ${LOG}
echo "${MATRIX_ARGS}"  | tr ';' '\n' | while IFS= read -r args; do
  if [ $(echo "${args}" | sed 's|.*-l ||;s| .*||' | tr ',' '\n' | grep '^all$' | wc -l) -gt 0 ] ; then
    OPTS=""
    case "${TEST_FLAVOR}" in
      high_stats ) ;;
      nano ) OPTS="-w nano" ;;
      * ) if is_in_array "${TEST_FLAVOR}" "${ALL_GPU_TYPES[@]}" ; then
            OPTS=$(get_gpu_matrix_args | sed -r 's|--gpu  *[a-z_-]+||')
          fi
          ;;
    esac
    ALL_WFS=$(runTheMatrix.py -n ${OPTS} ${args} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' | tr '\n' ',' | sed 's|,$||')
    args=$(echo "${args}" | sed "s|all|${ALL_WFS}|")
  fi
  dateBefore=$(date +"%s")
  (LOCALRT=${WORKSPACE}/${CMSSW_VERSION} EXTRA_MATRIX_COMMAND_ARGS="${RUN_THE_MATRIX_CMD_OPTS}" CHECK_WORKFLOWS=false UPLOAD_ARTIFACTS=false MATRIX_ARGS="$args" timeout $MATRIX_TIMEOUT ${CMS_BOT_DIR}/run-ib-pr-matrix.sh "${TEST_FLAVOR}" && echo ALL_OK) 2>&1 | tee ${LOG}.tmp
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
  for lfn in $(grep /store/ lfns.txt | sed 's|/user/cmsbuild/store/|/|;s|^.*/store/|/store/|' | sort | uniq) ; do
    echo "LFN=${lfn}" > $WORKSPACE/lfn-to-ibeos-${CNT}.prop
    let CNT=${CNT}+1
  done
popd

TEST_ERRORS=$(grep -ai -E "ERROR .*" ${LOG} | grep -v 'DAS QL ERROR' | grep -v 'ERROR failed to parse X509 proxy') || true
GENERAL_ERRORS=`grep -a "ALL_OK" ${LOG}` || true

RESULT_FILE_NAME=$(get_result_file_name relval "${TEST_FLAVOR}" report)
FAILED_FILE_NAME=$(get_result_file_name relval "${TEST_FLAVOR}" failed)

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the RelVals"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;ERROR,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/$(get_status_file_name relval "$TEST_FLAVOR")
  ALL_OK=false
  RELVALS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_MATRIX_FAIL -f ${LOG} --report-file ${RESULTS_DIR}/${RESULT_FILE_NAME} --report-url ${PR_RESULT_URL} $NO_POST
  if [ $(grep -E -v '##( Failed|) RelVals' ${RESULTS_DIR}/${RESULT_FILE_NAME} | grep -v '^ *$' | wc -l) -eq 0 ] ; then
    echo -e "## Failed RelVals\n\n\`\`\`\n${TEST_ERRORS}\n\`\`\`\n" > ${RESULTS_DIR}/${RESULT_FILE_NAME}
  fi
  if [ "${TEST_FLAVOR}" != "" ] ; then
    sed -i -e "s|## Failed RelVals|## Failed RelVals-${UC_TEST_FLAVOR}|;s|/runTheMatrix-results|/runTheMatrix${UC_TEST_FLAVOR}-results|g" ${RESULTS_DIR}/${RESULT_FILE_NAME}
    echo "RelVals-${UC_TEST_FLAVOR}" > ${RESULTS_DIR}/${FAILED_FILE_NAME}
  else
    echo "RelVals" > ${RESULTS_DIR}/${FAILED_FILE_NAME}
  fi
  mark_commit_status_all_prs "${GH_COMP_CONTEXT}" 'success' -d "Not run due to failure in relvals" ${MARK_OPTS}
else
  touch ${RESULTS_DIR}/${FAILED_FILE_NAME}
  touch ${RESULTS_DIR}/${RESULT_FILE_NAME}
  echo "no errors in the RelVals!!"
  echo "MATRIX${UC_TEST_FLAVOR}_TESTS;OK,Matrix ${UC_TEST_FLAVOR} Tests Outputs,See Logs,runTheMatrix${UC_TEST_FLAVOR}-results" >> ${RESULTS_DIR}/$(get_status_file_name relval "$TEST_FLAVOR")

  if [[ -s "$WORKSPACE/bad-workflow-lists.txt" ]]; then
    echo '**Invalid workflow lists**: ${\color{red}\Huge{\textsf{'$(cat $WORKSPACE/bad-workflow-lists.txt)'}}}$' >  ${RESULTS_DIR}/0a-bad-workflows-report.res
  fi

  if $DO_COMPARISON ; then
    echo "COMPARISON${UC_TEST_FLAVOR};QUEUED,Comparison ${UC_TEST_FLAVOR} with the baseline,See results,See results" >> ${RESULTS_DIR}/comparison${UC_TEST_FLAVOR}.txt
    TRIGGER_COMPARISON_FILE=$WORKSPACE/'comparison.properties'
    echo "Creating properties file $TRIGGER_COMPARISON_FILE"
    echo "RELEASE_FORMAT=${CMSSW_VERSION}" > $TRIGGER_COMPARISON_FILE
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
