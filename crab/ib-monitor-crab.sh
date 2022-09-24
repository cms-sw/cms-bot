#!/bin/bash -ex

trap report EXIT

report() {
   exit_code=$?
   if [ ${exit_code} -eq 0 ]; then
       echo "PASSED" > $WORKSPACE/results/statusfile
   else
       echo "FAILED" > $WORKSPACE/results/statusfile
   fi
}

[ "${WORKSPACE}" != "" ] || export WORKSPACE=$(pwd) && cd $WORKSPACE
export ID=$(id -u)

CRAB_BUILD_ID=$1
GRIDSITE=$2

# Keep checking the status of the job until it finishes
voms-proxy-init -voms cms
status=""
while [ "${status}" = "" ]
do
  curl -s -L -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "${GRIDSITE}/status_cache" > $WORKSPACE/status.log 2>&1
  cat $WORKSPACE/status.log
  errval=$(grep -o "404 Not Found" $WORKSPACE/status.log || echo "")
  cat $WORKSPACE/status.log >> $WORKSPACE/results/logfile
  if [ "$errval" = "" ] ; then
    # Keep checking until job finishes
    status=$(grep -Eo "'State': '(finished|failed)'" $WORKSPACE/status.log || echo "")
  fi
  sleep 300
done
