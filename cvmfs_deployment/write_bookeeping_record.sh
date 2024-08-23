#!/bin/bash -ex

PACKAGE_NAME=$1
ARCH=$2
INSTALL_TYPE=$3 #can be package or data

tstamp=$(echo $(date +%s --utc) $(date --utc))

if [[ $INSTALL_TYPE == "package" ]] ; then
    pkg=$(echo $PACKAGE_NAME | cut -d+ -f2)
    version=$(echo $PACKAGE_NAME | cut -d+ -f3)
    if [[ $pkg = "python" ]] ; then
	echo COMP+python+$version $ARCH $tstamp
    else
	echo $pkg $version $ARCH $tstamp
    fi
fi
