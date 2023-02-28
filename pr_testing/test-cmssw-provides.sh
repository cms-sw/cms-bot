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

RPM_CMD="/cvmfs/cms-ib.cern.ch/sw/$(uname -m)/week${WEEK_NUM}/common/cmspkg -a $SCRAM_ARCH env -- rpm"

if [ ! -d ${WORKSPACE}/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
  if [ ! -z ${CMSSW_FULL_RELEASE_BASE} ]; then
    CMSSW_RELEASE_PATCH=$CMSSW_RELEASE
    CMSSW_RELEASE=$(echo ${CMSSW_FULL_RELEASE_BASE} | rev | cut -d '/' -f 1 | rev)
  fi

  PROVIDELIST=$(${RPM_CMD} -q --provides cms+cmssw+${CMSSW_RELEASE})
  PROVIDELIST=$(echo $PROVIDELIST | sed -E 's/^(.*)$/Provides: \1/g')

  if [ ! -z ${CMSSW_RELEASE_PATCH} ]; then
    PROVIDELIST_PATCH=$(${RPM_CMD} -q --provides cms+cmssw-patch+${CMSSW_RELEASE_PATCH})
    PROVIDELIST_PATCH=$(echo ${PROVIDELIST_PATCH} | sed -E 's/^(.*)$/Provides: \1/g')
    PROVIDELIST="$PROVIDELIST\n${PROVIDELIST_PATCH}"
  fi
else
  PROVIDELIST=""
fi

cp $CMS_BOT_DIR/pr_testing/cmssw-pr-package.spec cmsdist/
sed -i -e "s!@release@!${WORKSPACE}/${CMSSW_RELEASE}!g" cmsdist/cmssw-pr-package.spec
sed -i -e "s!@provides@!${PROVIDELIST}!" cmsdist/cmssw-pr-package.spec

pushd ${WORKSPACE}/${CMSSW_RELEASE}
set +x
eval $(scram unsetenv -sh)
set -x
popd

# bootstrap cmsBuild
pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cms-common

if [ ! -d ${WORKSPACE}/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
    cp -r /cvmfs/cms-ib.cern.ch/sw/`uname -m`/week${WEEK_NUM}/${SCRAM_ARCH}/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
else
    cp -r ${WORKSPACE}/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm build/${SCRAM_ARCH}/var/lib/
fi

pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cmssw-pr-package
