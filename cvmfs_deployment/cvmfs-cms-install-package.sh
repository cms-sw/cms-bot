#!/bin/bash -ex

#  vars set because some functions are using them
INSTALL_PATH=$1
ARCHITECTURE=$2
RPMS_REPO=$3
PACKAGE_NAME=$4
REINSTALL=$5

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] || [ -z "$4" ] ; then
    echo "empty var, set it up, exit"
exit -1
fi

if [ "$REINSTALL" = true ] ; then
    REINSTALL="--reinstall"
else
    REINSTALL=""
fi

if [ ! -d $INSTALL_PATH ] ; then
    mkdir -p $INSTALL_PATH
fi

#  check if RPMS_REPO matches the one in install path
if [[ -f ${INSTALL_PATH}/common/cmspkg ]] &&  [[ `grep "repository ${RPMS_REPO}" ${INSTALL_PATH}/common/cmspkg | wc -l` -ne "1" ]]; then
    echo "Install path is bootstraped for another RPM REPO, abort"
    exit -1
fi


SCRAM_ARCH=$ARCHITECTURE #  for dockerrun function
#  PROOT_DIR= jenkins machine variable
#  CMS_BOT_DIR= jenkins machine variable, repo on cvmfs

#  proot have to exist, so setup it first if it doesn't. proot is a program if you wonder again what is this thing
${CMS_BOT_DIR}/cvmfs_deployment/install_proot.sh
#  get dockerrun function
source ${CMS_BOT_DIR}/cvmfs_deployment/docker_proot_function.sh

#  check bootstrap
${CMS_BOT_DIR}/cvmfs_deployment/bootstrap_dir_for_arch.sh $INSTALL_PATH $ARCHITECTURE $RPMS_REPO

#  check how many packages are available
number_of_matches=$(dockerrun "${INSTALL_PATH}/common/cmspkg -a ${ARCHITECTURE} search ${PACKAGE_NAME} | sed -e 's|[ ].*||' | grep -e '^${PACKAGE_NAME}\$' | wc -l" | wc -l )
echo "   number of search matches: $number_of_matches"
echo "   lenght of variable: ${#number_of_matches} "

#  package should be only 1, see if not equal to 1. All > 1 is ambiguous
if [[ $number_of_matches == 1 ]] ; then
#  install the package if it's available
    echo '  pkg found, install it'
    pwd
    dockerrun "${INSTALL_PATH}/common/cmspkg -a ${ARCHITECTURE} ${REINSTALL} install -y ${PACKAGE_NAME} -p ${INSTALL_PATH}"
else
#  or, print the package was not found
echo '  pkg not found or more than one found (leading to ambiguity)'
fi
