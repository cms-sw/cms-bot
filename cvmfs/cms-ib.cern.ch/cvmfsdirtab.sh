#!/bin/bash
dirtab=$(dirname $0)/cvmfsdirtab.txt
if [ -f "${dirtab}" ] ; then cat "${dirtab}" ; fi
$(dirname $0)/../cvmfsdirtab.sh 'nweek-*' 'tests' 
