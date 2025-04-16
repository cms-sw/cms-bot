#!/bin/bash -ex
cd /tmp
lock=~/cron_install_cmssw.lock
ERR=0
cvmfs_server publish ${CVMFS_REPOSITORY} || ERR=1
if [ "$ERR" = "1" ] ; then cvmfs_server abort -f ${CVMFS_REPOSITORY} || ERR=1 ; fi
rm -f $lock
exit $ERR
