#!/bin/bash -ex

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

exit 0
#cvmfs_server trasaction || cvmfs_server abort && cvmfs_server transaction