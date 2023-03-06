#!/bin/bash -xe
if [ $# -ne 4 ]; then
  echo Usage: $0 pkgtools_branch cmsdist_tag build_dir week_num
  exit 1
fi

PKG_TOOL_BRANCH=$1
CMSDIST_TAG=$2
BUILD_DIR=$3
WEEK_NUM=$4

#Prepare cmsdist/pkgtool/test directories and generate cmssw-pr-package spec file
[ -d $WORKSPACE/pkgtools ] && ln -s $WORKSPACE/pkgtools . || git clone git@github.com:cms-sw/pkgtools --depth 1 -b $PKG_TOOL_BRANCH
[ -d $WORKSPACE/cmsdist ]  && ln -s $WORKSPACE/cmsdist .  || git clone git@github.com:cms-sw/cmsdist  --depth 1 -b $CMSDIST_TAG
echo "%define release_dir ${CMSSW_BASE}" > cmsdist/cmssw-pr-data.file
cp $(dirname $0)/cmssw-pr-package.spec cmsdist/
rm -rf $WORKSPACE/test-provides ; mkdir -p $WORKSPACE/test-provides ; cd $WORKSPACE/test-provides

#Get cmssw/cmssw-patch release RPM Provides if PR has built cmssw-tool-conf locally
#otherwise we copy the complete RPM DB from release area
RELEASE_BASEDIR=/cvmfs/cms-ib.cern.ch/sw/$(uname -m)/week${WEEK_NUM}
if [ -d $WORKSPACE/$BUILD_DIR/$SCRAM_ARCH/var/lib/rpm ]; then
  CMSSW_PKGS="cms+cmssw+$(basename $CMSSW_BASE)"
  [ ! -z ${CMSSW_FULL_RELEASE_BASE} ] && CMSSW_PKGS="cms+cmssw+$(basename $CMSSW_FULL_RELEASE_BASE) cms+cmssw-patch+$(basename $CMSSW_BASE)"
  ${RELEASE_BASEDIR}/common/cmspkg -a $SCRAM_ARCH env -- rpm -q --provides ${CMSSW_PKGS} | sed -E 's/^(.*)$/Provides: \1/' >> cmsdist/cmssw-pr-data.file
  RELEASE_BASEDIR=${WORKSPACE}/$BUILD_DIR
fi

#unset CMSSW env as cmsBuild should use system python instead of cmssw python
#Bootstrap local test area, copy RPM DB (for missing provides) and build cmssw-pr-package
set +x; eval $(scram unsetenv -sh) ;set -x
./pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -i build_dir build cms-common
cp -r ${RELEASE_BASEDIR}/$SCRAM_ARCH/var/lib/rpm build_dir/${SCRAM_ARCH}/var/lib/
./pkgtools/cmsBuild --repo cms.week${WEEK_NUM} -a $SCRAM_ARCH -i build_dir build cmssw-pr-package
