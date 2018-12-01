#!/bin/bash -ex

lock=~/cron_install_cmssw.lock
ERR=0
cvmfs_server publish || ERR=1
rm -f $lock
if [ "$ERR" = "1" ] ; then  cvmfs_server abort ; fi
exit $ERR
