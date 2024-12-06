#!/bin/bash -ex
pwd
ls
env > run.log
cmsRun -j FrameworkJobReport.xml -p PSet.py
