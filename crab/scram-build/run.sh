#!/bin/bash -x
log="$CMSSW_BASE/run.log"
ld.so --help | grep supported | grep x86-64-v
pushd $CMSSW_BASE
  sed -i -e 's|</tool>|  <flags REM_CUDA_HOST_CXXFLAGS="-march=%"/>\n  <flags CUDA_HOST_CXXFLAGS="-march=x86-64-v2"/>\n</tool>|' config/toolbox/${SCRAM_ARCH}/tools/selected/cuda.xml
  sed -i -e 's|</tool>|  <flags REM_ROCM_HOST_CXXFLAGS="-march=%"/>\n  <flags ROCM_HOST_CXXFLAGS="-march=x86-64-v2"/>\n</tool>|' config/toolbox/${SCRAM_ARCH}/tools/selected/rocm.xml
  git clone --depth 1 -b multi-targets https://github.com/cms-sw/cmssw-config >$log 2>&1
  rm -rf config/SCRAM
  mv cmssw-config/SCRAM config/SCRAM
  rm -rf cmssw-config
  scram setup cuda >>$log 2>&1
  scram setup rocm >>$log 2>&1
  scram b clean >>$log 2>&1
  scram build enable-multi-targets >>$log 2>&1
  rm -rf src
  for pkg in FWCore/Framework DataFormats ; do
    mkdir -p src/$pkg
    rsync -a --no-g $CMSSW_RELEASE_BASE/src/$pkg/ src/$pkg/
  done
  scram b -v -k -j $(nproc) >>$log 2>&1
  cat $log
  eval `scram run -sh`
  mkdir matrix
  pushd matrix
    runTheMatrix.py --job-reports --command " -n 5 --customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary " \
                    -i all -s -j 1 --ibeos >>$log 2>&1 || touch runall-report-step123-.log
    for f in $(find . -name '*' -type f) ; do
      case $f in
        *.xml|*.txt|*.log|*.py|*.json|*/cmdLog ) ;;
        * ) rm -rf $f ;;
      esac
    done
  popd
  mv matrix/runall-report-step123-.log matrix.log
  cat matrix.log >>$log
  cat matrix.log
  tar -czvf matrix.tar.gz matrix >>$log 2>&1
popd
[ -f run.log ] || mv $log .
[ -f matrix.tar.gz ] || mv $CMSSW_BASE/matrix.tar.gz .
[ -f matrix.log ] || mv $CMSSW_BASE/matrix.log .
