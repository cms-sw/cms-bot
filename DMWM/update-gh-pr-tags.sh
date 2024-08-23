#! /bin/bash -e

pushd code
git fetch --tags  https://github.com/dmwm/$CODE_REPO.git "+refs/heads/*:refs/remotes/origin/*"
git config remote.origin.url https://github.com/dmwm/$CODE_REPO.git
git config --add remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
git fetch --tags  https://github.com/dmwm/$CODE_REPO.git "+refs/pull/*:refs/remotes/origin/pr/*"
export COMMIT=`git rev-parse "origin/pr/$ghprbPullId/merge^{commit}"`

git checkout ${ghprbTargetBranch} # pick this up for later comparison in diff
git checkout -f $COMMIT


