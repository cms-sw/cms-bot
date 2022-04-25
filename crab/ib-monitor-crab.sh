#!/bin/bash -ex
WORKSPACE=$1
ID=$2
GRIDSITE=$3

# Keep checking the status of the job until it finishes
status=""
while [ "${status}" = "" ]
do
  sleep 300
  curl -s -L -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "${GRIDSITE}/status_cache" > $WORKSPACE/status.log 2>&1
  cat $WORKSPACE/status.log
  errval=$(grep -o "404 Not Found" $WORKSPACE/status.log || echo "")
  cat $WORKSPACE/status.log >> $WORKSPACE/crab/results/logfile
  if [ "$errval" = "" ] ; then
    # Keep checking until job finishes
    status=$(grep -o "'State': 'finished'" $WORKSPACE/status.log || echo "")
  fi
done
echo "PASSED" > $WORKSPACE/crab/statusfile
