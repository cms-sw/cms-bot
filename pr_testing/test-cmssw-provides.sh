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

CMSSW_RELEASE_BASE=${CMSSW_RELEASE}

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

if [ -d ${WORKSPACE}/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
  RPM_CMD="/cvmfs/cms-ib.cern.ch/sw/$(uname -m)/week${WEEK_NUM}/common/cmspkg -a $SCRAM_ARCH env -- rpm"
  if [ ! -z ${CMSSW_FULL_RELEASE_BASE} ]; then
    CMSSW_RELEASE_PATCH=$CMSSW_RELEASE
    CMSSW_RELEASE_BASE=$(echo ${CMSSW_FULL_RELEASE_BASE} | rev | cut -d '/' -f 1 | rev)
  fi

  ${RPM_CMD} -q --provides cms+cmssw+${CMSSW_RELEASE_BASE} | sed -E 's/^(.*)$/Provides: \1/g' > cmsdist/cmssw-pr-provides.file
  
  if [ ! -z ${CMSSW_RELEASE_PATCH} ]; then
    ${RPM_CMD} -q --provides cms+cmssw-patch+${CMSSW_RELEASE_PATCH} | sed -E 's/^(.*)$/Provides: \1/g' >> cmsdist/cmssw-pr-provides.file
  fi
  RPM_DB_PATH=${WORKSPACE}/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm
else
  PROVIDELIST=""
  RPM_DB_PATH=/cvmfs/cms-ib.cern.ch/sw/`uname -m`/week${WEEK_NUM}/${SCRAM_ARCH}/var/lib/rpm
fi

cp $CMS_BOT_DIR/pr_testing/cmssw-pr-package.spec cmsdist/
echo "%define release_dir ${WORKSPACE}/${CMSSW_RELEASE}" > cmsdist/cmssw-pr-defines.file
echo "${PROVIDELIST}" > cmsdist/cmssw-pr-provides.file
echo "${PROVIDELIST_PATCH}" >> cmsdist/cmssw-pr-provides.file

pushd ${WORKSPACE}/${CMSSW_RELEASE}
set +x
eval $(scram unsetenv -sh)
set -x
popd

# bootstrap cmsBuild
pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cms-common

# copy RPM database
cp -r ${RPM_DB_PATH} build/${SCRAM_ARCH}/var/lib/

pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -c cmsdist -i build --builders 1 -j 8 build cmssw-pr-package
