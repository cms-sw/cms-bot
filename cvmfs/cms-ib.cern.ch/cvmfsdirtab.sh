#!/bin/bash
[ "${CVMFS_DIR}" != "" ] || CVMFS_DIR="/cvmfs/$(basename $(dirname $0))"
export CVMFS_DIR
dirtab=$(dirname $0)/cvmfsdirtab.txt
if [ -f "${dirtab}" ] ; then cat "${dirtab}" ; fi
$(dirname $0)/../cvmfsdirtab.sh 'nweek-*' 'sw/*/nweek-*' 'tests'
