#!/bin/bash -ex
pwd
ls
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help >>run.log
