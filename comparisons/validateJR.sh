#!/bin/bash -x

baseA=$1
baseB=$2

if which python3 ; then
    python3 `dirname $0`/validateJR.py --base $baseA --ref $baseB --procs $(nproc)
else
    python `dirname $0`/validateJR.py --base $baseA --ref $baseB --procs $(nproc)
fi
