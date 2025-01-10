#!/bin/bash -x
log="run.log"
ld.so --help | grep supported | grep x86-64-v
pushd $CMSSW_BASE
  sed -i -e 's|</tool>|  <flags REM_CUDA_HOST_CXXFLAGS="-march=%"/>\n  <flags CUDA_HOST_CXXFLAGS="-march=x86-64-v2"/>\n</tool>|' config/toolbox/${SCRAM_ARCH}/tools/selected/cuda.xml
  sed -i -e 's|</tool>|  <flags REM_ROCM_HOST_CXXFLAGS="-march=%"/>\n  <flags ROCM_HOST_CXXFLAGS="-march=x86-64-v2"/>\n</tool>|' config/toolbox/${SCRAM_ARCH}/tools/selected/rocm.xml
  git clone --depth 1 -b multi-targets  https://github.com/cms-sw/cmssw-config >$log 2>&1
  rm -rf config/SCRAM
  mv cmssw-config/SCRAM config/SCRAM
  rm -rf cmssw-config
  scram setup cuda >>$log 2>&1
  scram setup rocm >>$log 2>&1
  scram b clean >>$log 2>&1
  scram build enable-multi-targets >>$log 2>&1
  rm -rf src
  for pkg in FWCore/Framework DataFormats GeneratorInterface/RivetInterface Geometry BigProducts/Simulation SimG4CMS SimG4Core HeterogeneousTest HeterogeneousCore ; do
    mkdir -p src/$pkg
    rsync -a --no-g $CMSSW_RELEASE_BASE/src/$pkg/ src/$pkg/
  done
  scram b -v -k -j $(nproc) >>$log 2>&1
  cat $log
  eval `scram run -sh`
  echo $LD_LIBRARY_PATH | tr : '\n'
  echo $PATH | tr : '\n'
  which edmPluginDump
  edmPluginDump -a >>$log
  which cmsRun
  cmsRun --help >>$log
  for d in lib biglib bin test ; do
    echo "======= $d =======" >>$log
    [ -d $d ] || continue
    find lib -type f >>$log
  done
popd
mv $CMSSW_BASE/$log .
