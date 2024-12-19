#!/bin/bash -x
log="run.log"
ld.so --help | grep supported | grep x86-64-v
pushd $CMSSW_BASE
  scram b clean
  scram build enable-multi-targets
  rm -rf src
  for pkg in FWCore/Framework DataFormats/Common ; do
    mkdir -p src/$pkg
    rsync -a --no-g $CMSSW_RELEASE_BASE/src/$pkg/ src/$pkg/
  done
  scram b -v -k -j $(nproc) >$log 2>&1
  cat $log
  eval `scram run -sh`
  echo $LD_LIBRARY_PATH | tr : '\n'
  echo $PATH | tr : '\n'
  which edmPluginDump
  edmPluginDump -a >>$log
  which cmsRun
  cmsRun --help >>$log
popd
mv $CMSSW_BASE/$log .
