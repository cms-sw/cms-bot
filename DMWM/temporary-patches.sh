#! /bin/bash -e

pushd deployment
git remote add ewv https://github.com/ericvaandering/deployment.git || true
git fetch ewv
git cherry-pick 2368295b048f9a343ab8023495a8a942f84a0539 || true
popd

echo "All temporary patches applied"
