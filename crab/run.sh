#!/bin/bash -e
echo "======  SCRAM Env ============="
env
echo "==============================="
ldd $(which cmsRun)
echo $LD_LIBRARY_PATH | tr : '\n'
cmsRun -j FrameworkJobReport.xml -p PSet.py
