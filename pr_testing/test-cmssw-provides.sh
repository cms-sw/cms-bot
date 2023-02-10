#!/bin/bash
if [ $# -ne 6 ]; then
  echo Usage: test-cmssw-provides.sh scram_arch pkgtools_branch cmsdist_tag build_dir week_num cmssw_release
  exit 1
fi

SCRAM_ARCH=$1
PKG_TOOL_BRANCH=$2
CMSDIST_TAG=$3
BUILD_DIR=$4
WEEK_NUM=$5
CMSSW_RELEASE=$6

SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path

rm -rf $WORKSPACE/test-provides
mkdir -p $WORKSPACE/test-provides
cd $WORKSPACE/test-provides
if [ ! -d $WORKSPACE/pkgtools ]; then
  git clone git@github.com:cms-sw/pkgtools --depth 1 -b $PKG_TOOL_BRANCH
else
  ln -s $WORKSPACE/pkgtools .
fi

if [ ! -d $WORKSPACE/cmsdist ]; then
  git clone git@github.com:cms-sw/cmsdist --depth 1 -b $CMSDIST_TAG
else
  ln -s $WORKSPACE/cmsdist .
fi

sed -ie "s!@release@!${WORKSPACE}/test-provides/${CMSSW_RELEASE}!g" cmssw-pr-package.spec
cp $CMS_BOT_DIR/cmssw-pr-package.spec cmsdist/

mkdir -p var/lib

if [ ! -d $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
    cp -r /cvmfs/cms-ib.cern.ch/sw/`uname -m`/week${WEEK_NUM}/${SCRAM_ARCH}/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
else
    cp -r $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
fi

pkgtools/cmsBuild --weekly -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cmssw-pr-package | tee requires.log
if [ $? -ne 0 ]; then
  num_missing=$(grep requires.log -e "is needed by"|wc -l)
  exit 1
fi

