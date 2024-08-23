#!/bin/bash -e
ls -drt ${_CONDOR_SCRATCH_DIR}/.condor_ssh_to_job_* 2>/dev/null | head -n -1 | xargs --no-run-if-empty echo rm -rf || true
SCRIPT_DIR=$(dirname $0)
MAX_CPUS=$(grep -i '^ *RequestCpus *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
MAX_MEMORY=$(grep -i '^ *RequestMemory *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
let MEMORY_PER_CPU="${MAX_MEMORY}/(${MAX_CPUS}*2)"
echo "start"  > auto-load
$SCRIPT_DIR/node-check.py ${MAX_CPUS} ${MEMORY_PER_CPU} > out.log 2>&1 &
sleep 1
while [ ! -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-stop ] ; do sleep 1 ; done
echo "exit"  > auto-load
wait
rm -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-stop
