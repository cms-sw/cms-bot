#! /bin/bash -e

# Install crab-dev RPM

mkdir crabdev
pushd crabdev/

export SCRAM_ARCH=$DMWM_ARCH
wget -O bootstrap.sh http://cmsrep.cern.ch/cmssw/$COMP_REPO/bootstrap.sh
sh bootstrap.sh -architecture $DMWM_ARCH -path `pwd` -repository $COMP_REPO setup
source $DMWM_ARCH/external/apt/*/etc/profile.d/init.sh
apt-get update
apt-get -y install cms+crab-devtools+${CRABDEV_LATEST}
source $DMWM_ARCH/cms/crab-devtools/${CRABDEV_LATEST}/etc/profile.d/init.sh
popd

