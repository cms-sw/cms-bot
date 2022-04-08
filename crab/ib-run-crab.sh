#!/bin/bash -ex
[ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
[ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
[ "${SINGULARITY_IMAGE}" != "" ] || export SINGULARITY_IMAGE="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel8-m"

export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
voms-proxy-init -voms cms
crab submit -c $(dirname $0)/task.py
crab status -d crab_${CRAB_REQUEST}
