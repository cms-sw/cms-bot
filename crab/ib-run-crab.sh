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
[ "${CRABCONFIGINSTANCE}" != "" ]|| export CRABCONFIGINSTANCE="prod"

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
rm -rf ${WORKSPACE}/crab
mv crab_${CRAB_REQUEST} ${WORKSPACE}/crab
echo "INPROGRESS" > $WORKSPACE/crab/statusfile

cat $WORKSPACE/crab/.requestcache 
export ID=$(id -u)
export TASK_ID=$(grep crab_${CRAB_REQUEST} $WORKSPACE/crab/.requestcache | sed 's|^V||')
export SUBMISSION_NAME=$(echo $TASK_ID | cut -d ":" -f2 | cut -d "_" -f2-)

if [ "${TASK_ID}" = "" ] ; then exit 1 ; fi

echo "Keep checking job information until grid site has been assigned"
GRIDSITE="N/Ayet"
while [ "${GRIDSITE}" = "N/Ayet" ]
do
  sleep 10
  echo "Gridsite has not been assigned yet!"
  export GRIDSITE=$(crab status -d ./crab | grep "Grid scheduler - Task Worker:" | cut -d ":" -f2 | cut -d "-" -f1 | tr -d '\t' | tr -d " ")
done

# Store information for the monitoring job
echo "CRAB_BUILD_ID=$BUILD_ID" >> $WORKSPACE/crab/parameters.property
GRIDSITE_NAME="http://$(echo $GRIDSITE | cut -d "@" -f2)/mon/cmsbot/${TASK_ID}"
echo "CRAB_GRIDSITE=$GRIDSITE_NAME" >> $WORKSPACE/crab/parameters.property
echo "RELEASE_FORMAT=$RELEASE_FORMAT" >> $WORKSPACE/crab/parameters.property
echo "ARCHITECTURE=$ARCHITECTURE" >> $WORKSPACE/crab/parameters.property
echo "PULL_REQUESTS=$PULL_REQUESTS" >> $WORKSPACE/crab/parameters.property
echo "PULL_REQUEST=$PULL_REQUEST" >> $WORKSPACE/crab/parameters.property
echo "PR_RESULT_URL=$PR_RESULT_URL" >> $WORKSPACE/crab/parameters.property
echo "ENV_LAST_PR_COMMIT=$LAST_PR_COMMIT" >> $WORKSPACE/crab/parameters.property
echo "CMSSW_QUEUE=$CMSSW_QUEUE" >> $WORKSPACE/crab/parameters.property
echo "CONTEXT_PREFIX=$CONTEXT_PREFIX" >> $WORKSPACE/crab/parameters.property
echo "UPLOAD_UNIQ_ID=$UPLOAD_UNIQ_ID" >> $WORKSPACE/crab/parameters.property
[ "$CRAB_SITE" = "" ] || echo "CRAB_SITE=$CRAB_SITE" >> $WORKSPACE/crab/parameters.property
