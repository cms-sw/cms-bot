#!/bin/bash -ex
CRABCLIENT_TYPE="prod"
[ "$1" = "" ] || CRABCLIENT_TYPE="$1"
[ "${BUILD_ID}" != "" ] || BUILD_ID=1

export CRABCLIENT_TYPE
export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
voms-proxy-init -voms cms
crab submit -c $(dirname $0)/task.py

crab status -d crab_${CRAB_REQUEST}

