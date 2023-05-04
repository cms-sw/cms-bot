#!/bin/bash
#This is a utility script which can go through your uncommited cmssw changes and separate them
#for each category. After running this script you will have cmssw/src-category directory which
#should only contain changes for that category. If a package belong to multiple cmssw categories
# your you will have src-catA-catB directory.
# your original changes will be copied in to src.orig directory.

function usage_and_exit(){
  echo "Usage: $0 '<commit-msg>' '<branch-suffix>'\n"
  echo "For example:"
  echo "$0 '[GCC12] Fix build warnings' 'gcc12-warn1'"
  exit 1
}

COMMIT="$1"
BRANCH="$2"

[ "${COMMIT}" = "" ] && usage_and_exit 
[ "${BRANCH}" = "" ] && usage_and_exit

SCRIPT_DIR=$(realpath $(dirname $0))
cd $CMSSW_BASE
scram b clean >/dev/null 2>&1
if [ ! -d src.orig ] ; then mv src src.orig ; fi
rm -rf src
if [ ! -d src.init ] ; then
  mkdir src
  git cms-init
  mv src src.init
fi
cd src.orig
git diff --name-only | ${SCRIPT_DIR}/../package2category.py | while read -r line ; do
  cat=$(echo $line | awk '{print $1}')
  [ ! -d $CMSSW_BASE/src-${cat} ] || continue
  ucat=$(echo $cat | tr '[a-z]' '[A-Z]')
  pkgs=$(echo $line | sed 's|^[^ ][^ ]* ||')
  pushd $CMSSW_BASE
    scram b clean >/dev/null 2>&1
    rm -rf src
    cp -r src.init src
    git cms-addpkg $pkgs
  popd
  for f in $(git diff --name-only) ; do
    [ -e ../src/$f ] || continue
    if [ -e $f ] ; then
      cp $f ../src/$f
    else
      rm -f ../src/$f 
    fi
  done
  pushd $CMSSW_BASE/src
    git commit -a -m "[${ucat}] $COMMIT"
    scram build -j 10 code-format
    if [ $(git diff --name-only | wc -l) -gt 0 ] ; then
      git commit -a -m 'apply code format'
    fi
    git checkout -b "${cat}-${BRANCH}"
    git push my-cmssw "${cat}-${BRANCH}"
  popd
  mv $CMSSW_BASE/src $CMSSW_BASE/src-${cat}
done
