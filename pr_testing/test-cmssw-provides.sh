#!/bin/bash -xe
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

set +x
eval $(scram unsetenv -sh)
set -x

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

sed -i -e "s!@release@!${WORKSPACE}/${CMSSW_RELEASE}!g" $CMS_BOT_DIR/pr_testing/cmssw-pr-package.spec
cp $CMS_BOT_DIR/pr_testing/cmssw-pr-package.spec cmsdist/

#mkdir -p test-provides/${SCRAM_ARCH}/var/lib
# bootstrap cmsBuild
pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cms-common

if [ ! -d $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
    cp -r /cvmfs/cms-ib.cern.ch/sw/`uname -m`/week${WEEK_NUM}/${SCRAM_ARCH}/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
else
    cp -r $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
fi

pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cmssw-pr-package

cd ${WORKSPACE}/${CMSSW_RELEASE}
set +x
eval $(scram runtime -sh)
set -x
