#!/bin/bash -ex
[ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
[ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
if [ "${SINGULARITY_IMAGE}" = "" ] ; then
  osver=$(echo ${SCRAM_ARCH} | tr '_' '\n' | head -1 | sed 's|^[a-z][a-z]*||')
  export SINGULARITY_IMAGE="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel${osver}"
fi

export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
voms-proxy-init -voms cms
crab submit -c $(dirname $0)/task.py

export ID=$(id -u)
export TASK_ID=$(grep crab_${CRAB_REQUEST} crab_${CRAB_REQUEST}/.requestcache | sed 's|^V||')

# Wait a few seconds to get the resources assigned
sleep 10

echo "Keep checking job information until grid site has been assigned"
GRIDSITE=""
while [ "${GRIDSITE}" = "" ]
do
  export GRIDSITE=$(curl -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "https://cmsweb.cern.ch:8443/crabserver/prod/task?subresource=search&workflow=${TASK_ID}" | grep -o "http://.*${TASK_ID}")
  sleep 5
done

# Wait a few seconds to start the monitoring of the job
sleep 10

echo "Wait until job has finished"
status=""
while [ "${status}" = "" ]
do
  output=$(curl -L -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "http://${GRIDSITE}/mon/cmsbot/${TASK_ID}/status_cache")
  errval=$(echo $output | grep -o "404 Not Found" || echo "")
  if [ "$errval" = "" ] ; then
    echo -e "["$(date)"]:" $output "\n" >> crab_${CRAB_REQUEST}/results/logfile
    # Keep checking until job finishes
    status=$(echo $output | grep -o "'State': 'finished'" || echo "")
    echo $status
  else
    echo -e "["$(date)"]: ERROR: Failed to curl job status\n" >> crab_${CRAB_REQUEST}/results/logfile
  fi
  sleep 30
done

echo "Job FINISHED"
echo "PASSED" > crab_${CRAB_REQUEST}/results/statusfile && exit 0
