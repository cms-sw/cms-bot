#!/bin/bash -e
ls -drt ${_CONDOR_SCRATCH_DIR}/.condor_ssh_to_job_* 2>/dev/null | head -n -1 | xargs --no-run-if-empty echo rm -rf || true
SCRIPT_DIR=$(dirname $0)
END_TIME=""
if [ "${MAX_RUMTIME}" != "" ] ; then
  START_TIME=$(date +%s)
  let END_TIME=${START_TIME}+${MAX_RUMTIME}
fi
MAX_CPUS=$(grep -i '^ *RequestCpus *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
MAX_MEMORY=$(grep -i '^ *RequestMemory *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
let MEMORY_PER_CPU="${MAX_MEMORY}/(${MAX_CPUS}+1)"
echo "start"  > auto-load
$SCRIPT_DIR/node-check.py ${MAX_CPUS} ${MEMORY_PER_CPU} > out.log 2>&1 &
sleep 1
while [ ! -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load ] ; do
  if [ "${END_TIME}" != "" ] ; then
    if [ $(date +%s) -gt $END_TIME ] ; then break ; fi
  fi
  sleep 1
done
echo "exit"  > auto-load
wait
if [ -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load ] ; then
  rm -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load
  touch ${_CONDOR_SCRATCH_DIR}/jenkins/.shut-down
fi
