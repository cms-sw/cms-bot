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

[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh
source $WORKSPACE/cms-bot/common/github_reports.sh

voms-proxy-init -voms cms

cd $RELEASE_FORMAT
eval `scram run -sh`
[ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
CRABCLIENT_TYPES=$(ls ${PR_CVMFS_PATH}/share/cms/ | grep -Eo '(dev|prod|pre)')
[ "${CRABCLIENT_TYPES}" != "" ] || CRABCLIENT_TYPES="prod"
for CRABCLIENT_TYPE in ${CRABCLIENT_TYPES}
do
    # Report PR status
    mark_commit_status_all_prs 'crab-'${CRABCLIENT_TYPE} 'pending' -u "${BUILD_URL}" -d "Running"
    echo "CRAB is sourced from:"
    which crab-${CRABCLIENT_TYPE}

    export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
    rm -rf crab_${CRAB_REQUEST}
    crab-${CRABCLIENT_TYPE} submit -c $(dirname $0)/task.py

    export ID=$(id -u)
    export TASK_ID=$(grep crab_${CRAB_REQUEST} crab_${CRAB_REQUEST}/.requestcache | sed 's|^V||')

    echo "Keep checking job information until grid site has been assigned"
    GRIDSITE=""
    while [ "${GRIDSITE}" = "" ]
    do
      sleep 10
      export GRIDSITE=$(curl -s -X GET --cert "/tmp/x509up_u${ID}" --key "/tmp/x509up_u${ID}" --capath "/etc/grid-security/certificates/" "https://cmsweb.cern.ch:8443/crabserver/prod/task?subresource=search&workflow=${TASK_ID}" | grep -o "http.*/${TASK_ID}")
    done

    # Store information for the monitoring job
    CRAB_PROP=$WORKSPACE/crab-${CRABCLIENT_TYPE}.property
    echo "CRAB_BUILD_ID=$BUILD_ID" > ${CRAB_PROP}
    echo "CRAB_GRIDSITE=$GRIDSITE" >> ${CRAB_PROP}
    echo "RELEASE_FORMAT=$RELEASE_FORMAT" >> ${CRAB_PROP}
    echo "ARCHITECTURE=$ARCHITECTURE" >> ${CRAB_PROP}
    echo "PULL_REQUESTS=$PULL_REQUESTS" >> ${CRAB_PROP}
    echo "PULL_REQUEST=$PULL_REQUEST" >> ${CRAB_PROP}
    echo "PR_RESULT_URL=$PR_RESULT_URL" >> ${CRAB_PROP}
    echo "ENV_LAST_PR_COMMIT=$LAST_PR_COMMIT" >> ${CRAB_PROP}
    echo "CMSSW_QUEUE=$CMSSW_QUEUE" >> ${CRAB_PROP}
    echo "CONTEXT_PREFIX=$CONTEXT_PREFIX" >> ${CRAB_PROP}
    echo "UPLOAD_UNIQ_ID=$UPLOAD_UNIQ_ID" >> ${CRAB_PROP}
    echo "CRABCLIENT_TYPE=$CRABCLIENT_TYPE" >> ${CRAB_PROP}

    # Clean workspace for next iteration
    rm -rf crab_${CRAB_REQUEST}
    ls $WORKSPACE
done
mark_commit_status_all_prs 'crab' 'success' -u "${BUILD_URL}" -d "CRAB test successfully triggered"
