#!/bin/bash -ex
log="run.log"
ld.so --help | grep supported | grep x86-64-v
pushd $CMSSW_BASE
  scram b clean
  scram build enable-multi-targets
  rm -rf src
  mkdir src
  git clone https://github.com/cms-sw/cmssw-config
  cd cmssw-config; git checkout V09-06-02 ; cd ..
  rm -rf config/SCRAM; mv cmssw-config/SCRAM config/SCRAM
  git cms-addpkg '*' > $log
  scram b -v -k -j $(nproc) >$log 2>&1 || true
  eval `scram run -sh`
  which edmPluginDump
  edmPluginDump -a >>$log || true
  which cmsRun
  cmsRun --help >>$log || true
popd
[ -f $log ] || mv $CMSSW_BASE/$log $log
cmsRun -j FrameworkJobReport.xml PSet.py || true
