#!/bin/bash -x
#for f in minbias.root FrameworkJobReport.xml ; do
#  curl -L -o $f http://cern.ch/muzaffar/$f
#  [ -e $f ] || exit 1
#done
#ls
env > run.log
echo "======================" >> run.log
pushd $CMSSW_BASE
  scram build disable-biglib
  if false ; then
  for dir in lib biglib ; do
    rm -rf $dir
    rsync -a $CMSSW_RELEASE_BASE/${dir}/ ./${dir}/ || true
    [ -d ${dir}/$SCRAM_ARCH/scram_x86-64-v2 ] || continue
    pushd ${dir}/$SCRAM_ARCH/scram_x86-64-v2
      for pcm in $(ls *.pcm) ; do
        rm -f $pcm
        cp ../$pcm .
      done
    popd
  done
  fi
  eval `scram run -sh`
pushd
#export LD_LIBRARY_PATH=$(echo $LD_LIBRARY_PATH | tr : '\n' | grep -E -v "$CMSSW_RELEASE_BASE/(big|)lib/" | grep -E -v "/${CMSSW_VERSION}/(big|)lib/${SCRAM_ARCH}$" | tr '\n' ':')
echo $LD_LIBRARY_PATH | tr : '\n'
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help
cmsRun -p FrameworkJobReport.xml PSet.py
