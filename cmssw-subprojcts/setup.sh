#!/bin/bash -ex
SUBPROJECT=$1
FILTER=$2
BRANCH=$3

if [ "X${BRANCH}" = "X" ] ; then BRANCH=master; fi

if [ "X${SUBPROJECT}" = "X" -o "X${FILTER}" = "X" ] ; then
  echo "Error: Missing sub-project name"
  echo "Usage: $0 <Stitch|FWLite> <filter-file>"
  exit 1
fi

if [ ! -e $FILTER ] ; then
  echo "Error: No such file: $FILTER"
  exit 1
fi

sed -e "s|@PROJECT@|${SUBPROJECT}|;s|@PROJECT_FILTER@|${FILTER}|;s|@BRANCH@|${BRANCH}|" $(dirname $0)/git_filter.cfg > ${SUBPROJECT}.cfg
git clone git@github.com:cms-sw/git_filter
pushd git_filter
  gmake -j $(nproc)
popd
git clone git@github.com:cms-sw/cmssw
./git_filter/git_filter ${SUBPROJECT}.cfg
cd cmssw
git repack -ad
set +x
echo "Please run the following commands to update the new repository"
echo "cd cmssw"
echo "git remote add ${SUBPROJECT} git@github.com:cms-sw/${SUBPROJECT}"
echo "git push -f ${SUBPROJECT} ${BRANCH}-${SUBPROJECT}:${BRANCH}"
