#!/bin/bash -ex
source $(dirname $0)/utils.sh
CVMFS_DIR=${CVMFS_BASEDIR}/git
cvmfs_transaction /git
for rep in ${REPOSITORY} ; do
  cd $WORKSPACE
  rm -rf checkout
  mkdir checkout
  cd checkout
  GH_REPO=${rep}.git
  REPO_NAME=$(basename ${GH_REPO})
  git clone --bare https://github.com/${GH_REPO} ${REPO_NAME}
  pushd ${REPO_NAME}
    git repack -a -d --window=50 --max-pack-size=64M
  popd
  mkdir -p $(dirname ${CVMFS_DIR}/${GH_REPO})
  rsync -a --delete ${REPO_NAME}/ ${CVMFS_DIR}/${GH_REPO}/
done
cvmfs_server publish
