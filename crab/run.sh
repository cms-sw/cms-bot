#!/bin/bash -ex
pwd
ls
env > run.log
cmsRun -j FrameworkJobReport.xml PSet.py
