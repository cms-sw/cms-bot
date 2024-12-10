#!/bin/bash -ex
pwd
ls
file input_files.tar.gz
gunzip input_files.tar.gz || true
ls
tar -xvf input_files.tar.gz || true
ls
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help >>run.log
