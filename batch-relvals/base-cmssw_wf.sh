#!/bin/bash

set -x

LSB_EXIT_IF_CWD_NOTEXIST=Y

export SCRAM_ARCH=slc6_amd64_gcc481
scram p RELEASE
cd RELEASE
eval $(scram r -sh)
mkdir matrixTests
cd matrixTests
runTheMatrix.py -i all -l NUM_WF

#copy the results
#find DIRECTORY -regex ".*log$" | xargs -I ARG rfcp ARG HOME_DIR/batch-workflows/outs/DIRECTORY
rsync -r DIRECTORY/*.log HOME_DIR/batch-workflows/outs/DIRECTORY
rsync DIRECTORY/cmdLog HOME_DIR/batch-workflows/outs/DIRECTORY
