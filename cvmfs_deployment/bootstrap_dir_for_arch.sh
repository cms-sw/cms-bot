#!/bin/bash -ex
#  bootstrap - check if it exists and install if doesn't

INSTALL_PATH=$1
ARCHITECTURE=$2
#PROOT_DIR=$3
RPMS_REPO=$3

#  docker run doesnt exist inside the script. source it

source ${CMS_BOT_DIR}/cvmfs_deployment/docker_proot_function.sh

if [ $(ls -al ${INSTALL_PATH}/${ARCHITECTURE}/external/rpm/*/etc/profile.d/init.sh 2>/dev/null 1>/dev/null ; echo $? ; ) -ne 0 ] ; then
    echo 'boostrap not found, installing'
    mkdir -p $INSTALL_PATH
    wget --tries=5 --waitretry=60 -O ${INSTALL_PATH}/bootstrap.sh http://cmsrep.cern.ch/cmssw/repos/bootstrap.sh
    dockerrun "sh -ex ${INSTALL_PATH}/bootstrap.sh -a ${ARCHITECTURE} -repository ${RPMS_REPO} -path ${INSTALL_PATH} setup"
fi
