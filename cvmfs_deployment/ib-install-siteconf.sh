#!/bin/bash -ex
git clone --depth 1  https://github.com/cms-sw/siteconf.git SITECONF
GIT_DIR=./SITECONF/.git git log -n 1 --pretty=format:"%H" > SITECONF/commit.id
hostname > SITECONF//stratum0
rm -rf ./SITECONF/.git
source $(dirname $0)/utils.sh
cvmfs_transaction SITECONF
rsync -av --delete SITECONF/ ${CVMFS_BASEDIR}/SITECONF/
time cvmfs_server publish
