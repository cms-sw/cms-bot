#!/bin/bash -ex

cvmfs_repo=cms-ib.cern.ch

lock=~/cron_install_cmssw.lock
CPID=""
while [ "$CPID" != "$1" ]  ; do
  while [ -f $lock ]; do
      echo wait some time
      sleep 30
  done
  echo $1 > $lock
  sleep 1
  CPID=$(cat $lock | tail -1)
done

cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/cvmfs/${cvmfs_repo}/is_publishing.lock) && cvmfs_server transaction)
