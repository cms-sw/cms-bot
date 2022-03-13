#!/bin/bash -ex
#  bootstrap - check if it exists and install if doesn't

INSTALL_PATH=$1
SCRAM_ARCH=$2
RPMS_REPO=$3

#  check if RPMS_REPO matches the one in install path
if [ -f ${INSTALL_PATH}/common/cmspkg ] && [ $(grep "repository ${RPMS_REPO} " ${INSTALL_PATH}/common/cmspkg | wc -l) -eq 0 ] ; then
    echo "Install path is bootstraped for another RPM REPO, abort"
    exit 1
fi

if [ ! -f ${INSTALL_PATH}/${SCRAM_ARCH}/cms/cms-common/1.0/etc/profile.d/init.sh ] ; then
    mkdir -p $INSTALL_PATH
    rm -f ${INSTALL_PATH}/bootstrap.sh
    OPTS=""
    if [ "${USE_DEV_CMSPKG}" = "true" ] ; then
      OPTS="-dev"
    fi
    wget --tries=5 --waitretry=60 -O ${INSTALL_PATH}/bootstrap.sh http://cmsrep.cern.ch/cmssw/bootstrap.sh
    source $(dirname $0)/../dockerrun.sh
    export CMSPKG_OS_COMMAND=""
    dockerrun "sh -ex ${INSTALL_PATH}/bootstrap.sh -a ${SCRAM_ARCH} ${OPTS} -repository ${RPMS_REPO} -path ${INSTALL_PATH} setup"
fi
