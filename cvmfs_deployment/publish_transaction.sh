#!/bin/bash -ex
cd /tmp
lock=~/cron_install_cmssw.lock
ERR=0
cvmfs_server publish || ERR=1
if [ "$ERR" = "1" ] ; then cvmfs_server abort -f || ERR=1 ; fi
rm -f $lock
exit $ERR
