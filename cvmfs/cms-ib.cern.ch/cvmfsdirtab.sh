#!/bin/bash
export CVMFS_DIR="/cvmfs/$(basename $(dirname $0))"
dirtab=$(dirname $0)/cvmfsdirtab.txt
if [ -f "${dirtab}" ] ; then cat "${dirtab}" ; fi
$(dirname $0)/../cvmfsdirtab.sh 'nweek-*' 'sw/*/nweek-*' 'tests'
