#!/bin/bash
JENKINS_PROCESS=$(pgrep 'java' -a  | egrep "^[0-9]+\s+java\s+[-]jar\s+${WORKSPACE}/slave.jar\s+" | wc -l)
if [ ${JENKINS_PROCESS} -gt 0 ] ; then
  if $CHECK_RUN ; then
    echo "[$(date)] Stopping node check job" >> node-check.status
    touch ${WORKSPACE}/.auto-stop
    wait
    CHECK_RUN=false
    echo "[$(date)] Stopped node check job" >> node-check.status
  fi
elif ! $CHECK_RUN ; then
  CHECK_RUN=true
  rm -f ${WORKSPACE}/.auto-stop
  echo "[$(date)] Starting node check job" >> node-check.status
  $WORKSPACE/cache/cms-bot/condor/tests/node-check.sh > node-check.log 2>&1 &
fi
