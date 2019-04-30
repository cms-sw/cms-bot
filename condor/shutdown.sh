#!/bin/bash -ex
JOBID=$(echo $1 | sed 's|\.[0-9]*$||')
echo "Trying to shutdown the node"
SCHEDD_NAME=$(condor_q ${JOBID}.0 -af:l GlobalJobId -global | grep '^GlobalJobId *=' | sed 's|.*= *||;s|#.*||')
export _CONDOR_SCHEDD_HOST=${SCHEDD_NAME}
export _CONDOR_CREDD_HOST=${SCHEDD_NAME}
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
condor_q || true
