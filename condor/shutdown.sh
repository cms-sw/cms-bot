#!/bin/bash -ex
JOBID=$(echo $1 | sed 's|\.[0-9]*$||')
echo "Trying to shutdown the node"
condor_q
timeout 300 condor_ssh_to_job ${JOBID} 'touch ./jenkins/.shut-down' || true
sleep 120
condor_rm ${JOBID} || true
condor_transfer_data $JOBID || true
condor_rm ${JOBID} || true
condor_q
