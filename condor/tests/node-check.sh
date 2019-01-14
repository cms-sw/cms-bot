#!/bin/bash -ex
SCRIPT_DIR=$(dirname $0)
START_TIME=$(date +%s)
MAX_RUMTIME=${MAX_RUMTIME-1800}
let END_TIME=${START_TIME}+${MAX_RUMTIME}
MAX_CPUS=$(grep -i '^ *RequestCpus *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
MAX_MEMORY=$(grep -i '^ *RequestMemory *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
let MEMORY_PER_CPU="${MAX_MEMORY}/(${MAX_CPUS}+1)"

echo "start"  > auto-load
$SCRIPT_DIR/node-check.py ${MAX_CPUS} ${MEMORY_PER_CPU} > out.log 2>&1 &
sleep 10

while [ ! -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load ] ; do
  if [ $(date +%s) -gt $END_TIME ] ; then break ; fi
  sleep 60
done
echo "exit"  > auto-load
wait
cat out.log
if [ -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load ] ; then
  rm -f ${_CONDOR_SCRATCH_DIR}/jenkins/.auto-load
  touch ${_CONDOR_SCRATCH_DIR}/jenkins/.shut-down
  echo "${GRID_NODE}.0" | sed 's|^grid|CONDOR_JOB_ID=|' > ${GRID_NODE}-shutdown.txt
  echo "STATUS=shutdown" >> ${GRID_NODE}-shutdown.txt
fi
