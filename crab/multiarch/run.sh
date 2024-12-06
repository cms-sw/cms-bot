#!/bin/bash -ex
pwd
ls
env > run.log
pushd $CMSSW_BASE
  rm -rf lib
  rsync -a $CMSSW_RELEASE_BASE/lib/ ./lib/ || true
  cd lib/$SCRAM_ARCH/scram_x86-64-v2
  for pcm in $(ls *.pcm) ; do
    rm -f $pcm
    cp ../$pcm .
  done
pushd
export LD_LIBRARY_PATH=$(echo $LD_LIBRARY_PATH | tr : '\n' | grep -E -v "$CMSSW_RELEASE_BASE/(big|)lib/" | grep -E -v "/${CMSSW_VERSION}/(big|)lib/${SCRAM_ARCH}$" | tr '\n' ':')
echo $LD_LIBRARY_PATH | tr : '\n'
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help || true
cmsRun -j FrameworkJobReport.xml PSet.py || true
