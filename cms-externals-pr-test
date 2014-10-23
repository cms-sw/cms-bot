#!/bin/sh -ex

env
CMSDIST_PATH=/build/cmsdist
PKGTOOLS_PATH=/build/pkgtools
SCRAM_ARCH=unknown
RELEASE_QUEUE=unknown
INTERACTIVE=${INTERACTIVE-}
JOBS=${JOBS-1}

while [ X$# != X0 ] ; do
  case $1 in
    -c) shift ; CMSDIST_PATH=$1 ; shift ;;
    -p) shift ; PKGTOOLS_PATH=$1 ; shift ;;
    -a) shift ; SCRAM_ARCH=$1 ; shift ;;
    -q) shift ; RELEASE_QUEUE=$1 ; shift ;;
    -i) shift ; INTERACTIVE=$1 ; shift ;;
    -j) shift ; JOBS=$1 ; shift ;;
    -pr) shift ; PR=$1 ; shift ;;
    *) shift ; echo unknown option ;;
  esac
done

eval `curl https://raw.githubusercontent.com/cms-sw/cms-bot/master/config.map | grep SCRAM_ARCH=$SCRAM_ARCH | grep RELEASE_QUEUE=$RELEASE_QUEUE`

pushd $PKGTOOLS_PATH ; git fetch origin ; git checkout $PKGTOOLS_TAG; popd
pushd $CMSDIST_PATH ; git remote -v ; strace git fetch origin $CMSDIST_TAG ; git checkout FETCH_HEAD; popd

BUILD_REPO=`echo $PR | sed -e 's|/.*||'`
BUILD_PACKAGE=`echo $PR | sed -e 's|.*/||;s|#.*||'`
BUILD_PR=`echo $PR | sed -e 's|.*#||'`
BUILD_PR_URL=`echo https://api.github.com/repos/$PR | sed -e "s|#|/pulls/|"`

# Find out basic details about the PR
BASE_REPO=`curl -s $BUILD_PR_URL  | jq '.["base"]["repo"]["clone_url"]' | sed -e 's/"//g'`
BASE_BRANCH=`curl -s $BUILD_PR_URL  | jq '.["base"]["ref"]' | sed -e 's/"//g'`

HEAD_REPO=`curl -s $BUILD_PR_URL | jq '.["head"]["repo"]["clone_url"]' | sed -e 's/"//g'`
HEAD_BRANCH=`curl -s $BUILD_PR_URL | jq '.["head"]["ref"]' | sed -e 's/"//g'`

# Clone the repository and merge the pull request.
git clone -b $BASE_BRANCH $BASE_REPO $BUILD_PACKAGE
pushd $BUILD_PACKAGE
  git config user.email "cmsbuild@cern.ch"
  git config user.name "CMS BOT"
  git pull $HEAD_REPO $HEAD_BRANCH
  HEAD_REF=`git rev-parse HEAD`
popd

perl -p -i -e "s|%define branch.*|%define branch ${BASE_BRANCH}|" cmsdist/${BUILD_PACKAGE}.spec
perl -p -i -e "s|%define tag.*|%define tag ${HEAD_REF}|" cmsdist/${BUILD_PACKAGE}.spec
perl -p -i -e "s|^Source.*|Source: git:/build/$BUILD_PACKAGE/.git?obj=${BASE_BRANCH}/%{tag}&export=%{n}-%{realversion}&output=/%{n}-%{realversion}-%{tag}.tgz|" cmsdist/${BUILD_PACKAGE}.spec

if [ X$INTERACTIVE = X1 ]; then
  echo "Run "
  echo
  echo pkgtools/cmsBuild -c cmsdist -a $SCRAM_ARCH -j $JOBS --work-dir w build $BUILD_PACKAGE
  echo
  echo to build
  bash
fi

pkgtools/cmsBuild -c cmsdist -a $SCRAM_ARCH -j $JOBS --work-dir w build $BUILD_PACKAGE
