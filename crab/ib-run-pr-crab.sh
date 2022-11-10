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

for CRABCLIENT_TYPE in $(ls ${PR_CVMFS_PATH}/share/cms/ | grep -Eo '(dev|prod|pre)')
do
    echo $CRABCLIENT_TYPE

    [ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
    [ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
    [ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE

    # Report PR status
    source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh
    source $WORKSPACE/cms-bot/common/github_reports.sh
    mark_commit_status_all_prs 'crab-'${CRABCLIENT_TYPE} 'pending' -u "${BUILD_URL}" -d "Running"
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

    # Store information for the monitoring job
    echo "CRAB_BUILD_ID=$BUILD_ID" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "CRAB_GRIDSITE=$GRIDSITE" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "RELEASE_FORMAT=$RELEASE_FORMAT" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "ARCHITECTURE=$ARCHITECTURE" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "PULL_REQUESTS=$PULL_REQUESTS" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "PULL_REQUEST=$PULL_REQUEST" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "PR_RESULT_URL=$PR_RESULT_URL" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "ENV_LAST_PR_COMMIT=$LAST_PR_COMMIT" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "CMSSW_QUEUE=$CMSSW_QUEUE" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "CONTEXT_PREFIX=$CONTEXT_PREFIX" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "UPLOAD_UNIQ_ID=$UPLOAD_UNIQ_ID" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property
    echo "CRABCLIENT_TYPE=$CRABCLIENT_TYPE" >> $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property

    # Clean workspace for next iteration
    cp $WORKSPACE/crab/statusfile $WORKSPACE/CRABTests-${CRABCLIENT_TYPE}
    mkdir $WORKSPACE/crab-${CRABCLIENT_TYPE}
    mv $WORKSPACE/CMSSW* $WORKSPACE/crab-${CRABCLIENT_TYPE} || true
    mv $WORKSPACE/crab/crab-${CRABCLIENT_TYPE}.property $WORKSPACE
    mv $WORKSPACE/crab $WORKSPACE/crab-${CRABCLIENT_TYPE} || true
    ls $WORKSPACE
done

DRY_RUN=""
NO_POST=""
prepare_upload_results

mark_commit_status_all_prs 'crab' 'success' -u "${BUILD_URL}" -d "CRAB test successfully triggered"
