#!/bin/bash
if [ $# -ne 6 ]; then
  echo Usage: test-cmssw-provides.sh scram_arch pkgtools_branch cmsdist_tag build_dir week_num cmssw_release
  exit 1
fi

mark_commit_status_all_prs "provides" 'pending' -u "${BUILD_URL}" -d "Waiting for tests to start"

SCRAM_ARCH=$1
PKG_TOOL_BRANCH=$2
CMSDIST_TAG=$3
BUILD_DIR=$4
WEEK_NUM=$5
CMSSW_RELEASE=$6

rm -rf $WORKSPACE/test-provides
mkdir -p $WORKSPACE/test-provides
cd $WORKSPACE/test-provides
git clone git@github.com:cms-sw/pkgtools -b $PKG_TOOL_BRANCH
git clone git@github.com:cms-sw/cmsdist -b $CMSDIST_TAG

sed -ie "s!@release@!${WORKSPACE}/test-provides/${CMSSW_RELEASE}!g" cmsdist/cmssw-pr-package.spec

mkdir -p var/lib

if [ ! -d $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
    cp -r /cvmfs/cms-ib.cern.ch/sw/x86_64/week${WEEK_NUM}/${SCRAM_ARCH}/var/lib/rpm var/lib
else
    cp -r $BUILD_DIR/$SCRAM_ARCH/var/lib/rpm var/lib
fi

scram project $CMSSW_RELEASE
pushd ${CMSSW_RELEASE}/src
    git cms-addpkg FWCore
    scram b -j8
popd

PKGTOOLS/cmsBuild --weekly -a el8_amd64_gcc11 -c CMSDIST -i BUILD --builders 1 -j 8 build cmssw-pr-package | tee requires.log
if [ $? -ne 0 ]; then
  num_missing=$(grep requires.log -e "is needed by"|wc -l)
  mark_commit_status_all_prs "provides" 'failed' -d "Failed: missing ${num_missing} Provides" -u "${BUILD_URL}"
  exit 1
fi

mark_commit_status_all_prs "provides" 'success' -d 'OK' -u "${BUILD_URL}"
