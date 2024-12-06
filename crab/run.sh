#!/bin/bash -ex
pwd
ls
env > run.log
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help
cmsRun -j FrameworkJobReport.xml PSet.py
