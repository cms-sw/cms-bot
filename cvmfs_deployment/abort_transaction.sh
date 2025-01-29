#!/bin/bash -ex
cd /tmp
lock=~/cron_install_cmssw.lock
rm -rf $lock

cvmfs_server abort -f ${CVMFS_REPOSITORY}
