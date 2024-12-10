#!/bin/bash -ex
pwd
ls $CMSSW_BASE || true
ls CMSSW_*/ || true
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help >>run.log
