#!/bin/bash -ex
[ "${WORKSPACE}" != "" ] || export WORKSPACE=$(pwd) && cd $WORKSPACE
echo "FAILED" > $WORKSPACE/results/statusfile
TEST_PASSED=false
export ID=$(id -u)

CRAB_BUILD_ID=$1
GRIDSITE=$2

# Keep checking the status of the job until it finishes
voms-proxy-init -voms cms
status=""
while true ; do
  curl -s -L -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "${GRIDSITE}/status_cache" > $WORKSPACE/status.log 2>&1
  cat $WORKSPACE/status.log
  errval=$(grep -o "404 Not Found" $WORKSPACE/status.log || echo "")
  cat $WORKSPACE/status.log >> $WORKSPACE/results/logfile
  if [ "$errval" = "" ] ; then
    # Keep checking until job finishes
    status=$(grep -Eo "'State': '(finished|failed)'" $WORKSPACE/status.log || echo "")
    [ "${status}" = "" ] || break
  fi
  sleep 300
done
if [ $(echo "${status}" | grep 'finished' | wc -l) -gt 0 ] ; then
  echo "PASSED" > $WORKSPACE/results/statusfile
  TEST_PASSED=true
fi

# Submit results to IB page (in case of IB test) or to github (in case of PR testing)
source $WORKSPACE/cms-bot/jenkins-artifacts

if [ -z ${RELEASE_NAME+x} ]; then
  # PR test
  if [ "X$TEST_PASSED" = Xfalse ]; then
    echo "Errors in CRAB PR test"
    echo 'CRAB_TESTS;ERROR,CRAB Tests,See Logs,CRABTests' >> $WORKSPACE/results/crab.txt
    CRAB_OK=false
    $CMS_BOT_DIR/report-pull-request-results PARSE_CRAB_FAIL -f $WORKSPACE/status.log --report-file $WORKSPACE/results/crab-report.res --report-url ${PR_RESULT_URL}
    echo "CRAB" > $WORKSPACE/results/crab-failed.res
  else
    echo "No errors in CRAB PR test"
    echo 'CRAB_TESTS;OK,CRAB Tests,See Logs,CRABTests' >> $WORKSPACE/results/crab.txt
    CRAB_OK=true
    touch $WORKSPACE/results/crab-failed.res
    touch $WORKSPACE/results/crab-report.res
  fi

  source $WORKSPACE/cms-bot/pr_testing/_helper_functions.sh
  source $WORKSPACE/cms-bot/common/github_reports.sh
  cp -rf $WORKSPACE/results $WORKSPACE/upload/crabTests
  prepare_upload_results
  
  if [ "X$CRAB_OK" = Xtrue ]; then
    mark_commit_status_all_prs 'crab' 'success' -u "${BUILD_URL}" -d "Passed"
  else
    mark_commit_status_all_prs 'crab' 'error' -u "${BUILD_URL}" -d "Errors in the CRABTests"
  fi
else
  # IB test
  ls -l $WORKSPACE/results
  send_jenkins_artifacts $WORKSPACE/results ib-run-crab/$RELEASE_FORMAT/$ARCHITECTURE/${CRAB_BUILD_ID}/
fi
