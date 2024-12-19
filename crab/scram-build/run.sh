#!/bin/bash -ex
log="run.log"
ld.so --help | grep supported | grep x86-64-v
pushd $CMSSW_BASE
  scram b clean
  scram build enable-multi-targets
  rm -rf src
  mkdir src
  git cms-addpkg FWCore/Framework DataFormats/Common  > $log
  scram b -v -k -j $(nproc) >$log 2>&1 || true
  eval `scram run -sh`
  which edmPluginDump
  edmPluginDump -a >>$log || true
  which cmsRun
  cmsRun --help >>$log || true
popd
