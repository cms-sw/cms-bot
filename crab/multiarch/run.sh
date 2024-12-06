#!/bin/bash -ex
pwd
ls
env > run.log
export LD_LIBRARY_PATH=$(echo $LD_LIBRARY_PATH | tr : '\n' | grep -E -v "/${CMSSW_VERSION}/(big|)lib/${SCRAM_ARCH}$" | tr '\n' ':')
echo $LD_LIBRARY_PATH | tr : '\n'
which cmsRun
cmsRun --help || true
cmsRun -j FrameworkJobReport.xml PSet.py || true
