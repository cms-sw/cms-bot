#!/bin/bash -ex

trap report EXIT

report() {
   exit_code=$?
   if [ ${exit_code} -ne 0 ]; then
       echo "FAILED" > $WORKSPACE/crab/statusfile
   fi
}

[ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
[ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE

if [ "${SINGULARITY_IMAGE}" = "" ] ; then
  osver=$(echo ${SCRAM_ARCH} | tr '_' '\n' | head -1 | sed 's|^[a-z][a-z]*||')
  ls /cvmfs/singularity.opensciencegrid.org >/dev/null 2>&1 || true
  IMG_PATH="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel${osver}"
  if [ ! -e "${IMG_PATH}" ] ; then
    IMG_PATH="/cvmfs/unpacked.cern.ch/registry.hub.docker.com/${DOCKER_IMG}"
  fi
  export SINGULARITY_IMAGE="${IMG_PATH}"
fi

export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
voms-proxy-init -voms cms
crab submit -c $(dirname $0)/task.py
mv crab_${CRAB_REQUEST} ${WORKSPACE}/crab
echo "INPROGRESS" > $WORKSPACE/crab/statusfile

export ID=$(id -u)
export TASK_ID=$(grep crab_${CRAB_REQUEST} $WORKSPACE/crab/.requestcache | sed 's|^V||')

echo "Keep checking job information until grid site has been assigned"
GRIDSITE=""
while [ "${GRIDSITE}" = "" ]
do
  sleep 10
  export GRIDSITE=$(curl -s -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "https://cmsweb.cern.ch:8443/crabserver/prod/task?subresource=search&workflow=${TASK_ID}" | grep -o "http.*/${TASK_ID}")
done

# Store information for the monitoring job
echo "CRAB_BUILD_ID=$BUILD_ID" >> $WORKSPACE/crab/parameters.property
echo "CRAB_GRIDSITE=$GRIDSITE" >> $WORKSPACE/crab/parameters.property
echo "RELEASE_FORMAT=$RELEASE_FORMAT" >> $WORKSPACE/crab/parameters.property
echo "ARCHITECTURE=$ARCHITECTURE" >> $WORKSPACE/crab/parameters.property
echo "PULL_REQUESTS=$PULL_REQUESTS" >> $WORKSPACE/crab/parameters.property
