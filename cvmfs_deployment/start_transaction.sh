#!/bin/bash -ex
cd /tmp
cvmfs_repo=${CVMFS_REPOSITORY}
if [ "$LOCK_CVMFS" != "false" ] ; then
  lock=~/cron_install_cmssw.lock
  CPID=""
  while [ "$CPID" != "JENKINS:$1" ]  ; do
    while [ -f $lock ] ; do
      if [ $(cat $lock | tail -1 | grep '^JENKINS:' | wc -l) -gt 0 ] ; then
        rm -f $lock
      else
        echo Waiting for lock ...
        sleep 30
      fi
    done
    echo "JENKINS:$1" > $lock
    sleep 1
    CPID=$(cat $lock | tail -1)
  done
fi

cvmfs_server transaction || ((cvmfs_server abort -f || rm -fR /var/spool/cvmfs/${cvmfs_repo}/is_publishing.lock) && cvmfs_server transaction)
