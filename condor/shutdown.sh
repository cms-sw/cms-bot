#!/bin/bash -ex
JOBID=$(echo $1 | sed 's|\.[0-9]*$||')
echo "Trying to shutdown the node"
condor_q
if [ $(condor_q ${JOBID} |  grep "^$(whoami) " | wc -l) -gt 0 ] ; then
  timeout 300 condor_ssh_to_job ${JOBID} 'touch ./jenkins/.shut-down' || true
  sleep 120
  condor_rm ${JOBID} || true
fi
mkdir -p $WORKSPACE/../grid-create-node/logs
condor_transfer_data $JOBID || true
cat $WORKSPACE/../grid-create-node/logs/log.* || true
rm -rf $WORKSPACE/../grid-create-node/logs
condor_rm  -forcex ${JOBID} || true
condor_q
