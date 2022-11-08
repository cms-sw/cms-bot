#!/bin/bash -ex

trap report EXIT

report() {
   exit_code=$?
   if [ ${exit_code} -ne 0 ]; then
       echo "FAILED" > $WORKSPACE/crab/statusfile
   fi
}

if [ "${SINGULARITY_IMAGE}" = "" ] ; then
  osver=$(echo ${SCRAM_ARCH} | tr '_' '\n' | head -1 | sed 's|^[a-z][a-z]*||')
  ls /cvmfs/singularity.opensciencegrid.org >/dev/null 2>&1 || true
  IMG_PATH="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel${osver}"
  if [ ! -e "${IMG_PATH}" ] ; then
    IMG_PATH="/cvmfs/unpacked.cern.ch/registry.hub.docker.com/${DOCKER_IMG}"
  fi
  export SINGULARITY_IMAGE="${IMG_PATH}"
fi

#CRABCLIENT_TYPE=$(ls ${PR_CVMFS_PATH}/share/cms/ | grep -Eo '(dev|prod|pre)')

ls $(pwd)/common | grep -Eo '(dev|prod|pre)' | while read -r line ; do
    CRABCLIENT_TYPE=$line

    [ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
    [ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
    [ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE

    echo "CRAB is sourced from:"
    which crab-${CRABCLIENT_TYPE}

    export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
    voms-proxy-init -voms cms
    crab-${CRABCLIENT_TYPE} submit -c $(dirname $0)/task.py
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

    # Trigger ib-crab-monitor job for each crab submit request
    os.environ.get("JENKINS_CLI_CMD")
        + " build ib-monitor-crab -p CRAB_BUILD_ID="
        + $BUILD_ID
        + " -p CRAB_GRIDSITE="
        + $GRIDSITE
        + " -p RELEASE_FORMAT="
        + $RELEASE_FORMAT
	+ " -p ARCHITECTURE="
        + $ARCHITECTURE
	+ " -p PULL_REQUESTS="
        + $PULL_REQUESTS
        + " -p PULL_REQUEST="
        + $PULL_REQUEST
        + " -p PR_RESULT_URL="
        + $PR_RESULT_URL
	+ " -p ENV_LAST_PR_COMMIT="
        + $LAST_PR_COMMIT
        + " -p CMSSW_QUEUE="
        + $CMSSW_QUEUE
        + " -p CONTEXT_PREFIX="
        + $CONTEXT_PREFIX
        + " -p UPLOAD_UNIQ_ID="
        + $UPLOAD_UNIQ_ID
        + " -p CRABCLIENT_TYPE="
        + $CRABCLIENT_TYPE
done
