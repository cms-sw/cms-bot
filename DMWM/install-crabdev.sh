#! /bin/bash -e

# Install crab-dev RPM

mkdir crabdev
pushd crabdev/
export REPO=comp.pre.mmascher
export SCRAM_ARCH=$DMWM_ARCH
wget -O bootstrap.sh http://cmsrep.cern.ch/cmssw/$REPO/bootstrap.sh
sh bootstrap.sh -architecture $DMWM_ARCH -path `pwd` -repository $REPO setup
source $DMWM_ARCH/external/apt/*/etc/profile.d/init.sh
apt-get update
apt-get -y install cms+crab-devtools+1.0-comp
source $DMWM_ARCH/cms/crab-devtools/1.0-comp/etc/profile.d/init.sh
popd

