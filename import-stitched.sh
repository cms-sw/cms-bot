#!/bin/bash -ex

CMSSW_TAG=$1
GIT_RELEASE=$2
DRY_RUN=$3
if [ "X$CMSSW_TAG" = "X" ] ; then
  echo "Usage: 0 CMSSW_version"
  exit 1
fi
if [ "X$GIT_RELEASE" != "X" ] ; then
  scram p $GIT_RELEASE
  pushd $GIT_RELEASE
    eval `scram runtime -sh`
  popd
fi

STITCHED_TAG=$(echo $CMSSW_TAG | sed 's|CMSSW_|STITCHED_|')

git clone git@github.com:cms-sw/Stitched.git
pushd Stitched
  HAS_TAG=$(git tag | grep "^$STITCHED_TAG"'$' | wc -l)
  if [ $HAS_TAG -gt 0 ] ; then
    echo "CMSSW tag  $CMSSW_TAG is already ported to stitched repo as $STITCHED_TAG"
    exit 0
  fi
  git checkout --orphan cmssw-tag
  git rm -rf .
popd

wget -O ${CMSSW_TAG}.tar.gz https://github.com/cms-sw/cmssw/archive/${CMSSW_TAG}.tar.gz
tar -xzf ${CMSSW_TAG}.tar.gz
rm -f ${CMSSW_TAG}.tar.gz
wget -O packages.txt https://raw.githubusercontent.com/cms-sw/Stitched/master/packages.txt

for pkg in $(cat packages.txt) ; do
  mkdir -p Stitched/$(dirname $pkg)
  mv cmssw-${CMSSW_TAG}/$pkg Stitched/$pkg
done
rm -rf cmssw-${CMSSW_TAG} ${GIT_RELEASE}

pushd Stitched
  git add .
  git commit -a -m "Imported new tag $STITCHED_TAG"
  git tag $STITCHED_TAG
  if [ "X$DRY_RUN" = "X" ] ; then
    git push origin $STITCHED_TAG
  fi
popd
