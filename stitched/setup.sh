#!/bin/bash -ex
cp $(dirname $0)/Stitched.* .
git clone git@github.com:cms-sw/git_filter
pushd git_filter
  gmake
popd
git clone git@github.com:cms-sw/cmssw
./git_filter/git_filter ./Stitched.cfg
cd cmssw
git repack -ad
set +x
echo "Please run the following commands to update the new repository"
echo "cd cmssw"
echo "git remote add Stitched git@github.com:cms-sw/Stitched"
echo "git push -f Stitched master-Stitched:master"
