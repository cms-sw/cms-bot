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
rm -f $WORKSPACE/status-${CRABCLIENT_TYPE}.log
if [ $(echo "${status}" | grep 'finished' | wc -l) -gt 0 ] ; then
  echo "PASSED" > $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE}
  TEST_PASSED=true
fi

# Submit testsResults to IB page (in case of IB test) or to github (in case of PR testing)
source $WORKSPACE/cms-bot/jenkins-artifacts

if [ "${UPLOAD_UNIQ_ID}" != "" ]; then
  # PR test
  mv $WORKSPACE/testsResults/crab-logfile-${CRABCLIENT_TYPE} $WORKSPACE/crab-${CRABCLIENT_TYPE}.log
  mv $WORKSPACE/testsResults/statusfile-${CRABCLIENT_TYPE} $WORKSPACE/crab-statusfile-${CRABCLIENT_TYPE}.log
  echo "Uploading results of PR testing"
  if ! $TEST_PASSED ; then
    echo "Errors in CRAB PR test"
    echo "CRAB_TESTS_${CRABCLIENT_TYPE};ERROR,CRAB ${CRABCLIENT_TYPE} Test,See Logs,crab-${CRABCLIENT_TYPE}.log" >> $WORKSPACE/testsResults/crab-${CRABCLIENT_TYPE}.txt
    echo "CRAB" > $WORKSPACE/testsResults/crab-failed-${CRABCLIENT_TYPE}.res
  else
    echo "No errors in CRAB PR test"
    echo "CRAB_TESTS_${CRABCLIENT_TYPE};OK,CRAB ${CRABCLIENT_TYPE} Test,See Logs,crab-${CRABCLIENT_TYPE}.log" >> $WORKSPACE/testsResults/crab-${CRABCLIENT_TYPE}.txt
    touch $WORKSPACE/testsResults/crab-failed-${CRABCLIENT_TYPE}.res
    touch $WORKSPACE/testsResults/crab-report-${CRABCLIENT_TYPE}.res
  fi

  source $WORKSPACE/cms-bot/pr_testing/_helper_functions.sh
  source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh
  source $WORKSPACE/cms-bot/common/github_reports.sh
  
  DRY_RUN=""
  NO_POST=""
  prepare_upload_results
  CMSSW_QUEUE=${CMSSW_QUEUE_FLAVOR}
  
  if $TEST_PASSED ; then
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
