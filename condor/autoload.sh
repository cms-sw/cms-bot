#!/bin/bash
SSH_JOBS=$(ls -d ${_CONDOR_SCRATCH_DIR}/.condor_ssh_to_job_* 2>/dev/null | wc -l)
if [ ${SSH_JOBS} -gt 0 ] ; then
  if $CHECK_RUN ; then
    ps -u $(whoami) -o pid,start_time,rss,size,pcpu,cmd --forest 2>&1  >> node-check.status
    echo "[$(date)] Stopping node check job" >> node-check.status
    touch ${WORKSPACE}/.auto-stop
    wait
    CHECK_RUN=false
    ps -u $(whoami) -o pid,start_time,cmd --forest 2>&1  >> node-check.status
    echo "[$(date)] Stopped node check job" >> node-check.status
  fi
elif ! $CHECK_RUN ; then
  CHECK_RUN=true
  ps -u $(whoami) -o pid,start_time,rss,size,pcpu,cmd --forest 2>&1  >> node-check.status
  rm -f ${WORKSPACE}/.auto-stop
  echo "[$(date)] Starting node check job" >> node-check.status
  $WORKSPACE/cache/cms-bot/condor/tests/node-check.sh > node-check.log 2>&1 &
fi
