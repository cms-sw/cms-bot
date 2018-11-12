#!/bin/bash -ex

lock=~/cron_install_cmssw.lock
rm -rf $lock
exit 0
cvmfs_server abort
