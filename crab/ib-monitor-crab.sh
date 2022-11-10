#!/bin/bash -ex
echo ${CRABCLIENT_TYPE}
export CMSSW_QUEUE_FLAVOR=${CMSSW_QUEUE}
[ "${WORKSPACE}" != "" ] || export WORKSPACE=$(pwd) && cd $WORKSPACE
echo "FAILED" > $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE}
TEST_PASSED=false
export ID=$(id -u)

CRAB_BUILD_ID=$1
GRIDSITE=$2

# Keep checking the status of the job until it finishes
voms-proxy-init -voms cms
status=""
while true ; do
  curl -s -L -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "${GRIDSITE}/status_cache" > $WORKSPACE/status-${CRABCLIENT_TYPE}.log 2>&1
  cat $WORKSPACE/status-${CRABCLIENT_TYPE}.log
  errval=$(grep -o "404 Not Found" $WORKSPACE/status-${CRABCLIENT_TYPE}.log || echo "")
  cat $WORKSPACE/status-${CRABCLIENT_TYPE}.log >> $WORKSPACE/testsResults/crab-logfile-${CRABCLIENT_TYPE}
  if [ "$errval" = "" ] ; then
    # Keep checking until job finishes
    status=$(grep -Eo "'State': '(finished|failed)'" $WORKSPACE/status-${CRABCLIENT_TYPE}.log || echo "")
    [ "${status}" = "" ] || break
  fi
  sleep 300
done
if [ $(echo "${status}" | grep 'finished' | wc -l) -gt 0 ] ; then
  echo "PASSED" > $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE}
  TEST_PASSED=true
fi

# Submit testsResults to IB page (in case of IB test) or to github (in case of PR testing)
source $WORKSPACE/cms-bot/jenkins-artifacts

if [ "${UPLOAD_UNIQ_ID}" != "" ]; then
  # PR test
  echo "Uploading results of PR testing"
  if [ "X$TEST_PASSED" = Xfalse ]; then
    echo "Errors in CRAB PR test"
    echo 'CRAB_TESTS;ERROR,CRAB Tests,See Logs,CRABTests-'${CRABCLIENT_TYPE} >> $WORKSPACE/testsResults/crab-${CRABCLIENT_TYPE}.txt
    CRAB_OK=false
    $CMS_BOT_DIR/report-pull-request-testsResults PARSE_CRAB_FAIL -f $WORKSPACE/status-${CRABCLIENT_TYPE}.log --report-file $WORKSPACE/testsResults/crab-report-${CRABCLIENT_TYPE}.res --report-url ${PR_RESULT_URL}
    echo "CRAB" > $WORKSPACE/testsResults/crab-failed-${CRABCLIENT_TYPE}.res
  else
    echo "No errors in CRAB PR test"
    echo 'CRAB_TESTS;OK,CRAB Tests,See Logs,CRABTests-'${CRABCLIENT_TYPE} >> $WORKSPACE/testsResults/crab-${CRABCLIENT_TYPE}.txt
    CRAB_OK=true
    touch $WORKSPACE/testsResults/crab-failed-${CRABCLIENT_TYPE}.res
    touch $WORKSPACE/testsResults/crab-report-${CRABCLIENT_TYPE}.res
  fi

  source $WORKSPACE/cms-bot/pr_testing/_helper_functions.sh
  source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh
  source $WORKSPACE/cms-bot/common/github_reports.sh
  rm $WORKSPACE/status-${CRABCLIENT_TYPE}.log
  mv $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE} $WORKSPACE/CRABTests-${CRABCLIENT_TYPE}
  
  DRY_RUN=""
  NO_POST=""
  prepare_upload_results
  CMSSW_QUEUE=${CMSSW_QUEUE_FLAVOR}
  
  if [ "X$CRAB_OK" = Xtrue ]; then
    mark_commit_status_all_prs 'crab-'${CRABCLIENT_TYPE} 'success' -u "${BUILD_URL}" -d "Passed"
  else
    mark_commit_status_all_prs 'crab-'${CRABCLIENT_TYPE} 'error' -u "${BUILD_URL}" -d "Errors found when testing CRAB"
  fi
else
  # IB test
  echo "Uploading results to IB page"
  mv $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE} $WORKSPACE/testsResults/statusfile
  mv $WORKSPACE/testsResults/crab-logfile-${CRABCLIENT_TYPE} $WORKSPACE/testsResults/monitor.log
  ls -l $WORKSPACE/testsResults
  send_jenkins_artifacts $WORKSPACE/testsResults ib-run-crab/$RELEASE_FORMAT/$ARCHITECTURE/${CRAB_BUILD_ID}/
fi
