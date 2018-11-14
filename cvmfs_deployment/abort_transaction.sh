#!/bin/bash -ex

lock=~/cron_install_cmssw.lock
rm -rf $lock

cvmfs_server abort -f
