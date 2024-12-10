#!/bin/bash -ex
pwd
ls
tar -xzvf input_files.tar.gz || true
ls
cat job_input_file_list_1.txt || true
ld.so --help | grep supported | grep x86-64-v
which cmsRun
cmsRun --help >>run.log
