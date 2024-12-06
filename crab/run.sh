#!/bin/bash -ex
pwd
ls
env > run.log
which cmsRun
cmsRun --help
cmsRun -j FrameworkJobReport.xml PSet.py
