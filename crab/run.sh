#!/bin/bash -ex
env > run.log
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun -j FrameworkJobReport.xml PSet.py >>run.log 2>&1
