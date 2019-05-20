#!/bin/bash -ex

SUBPROJECT=""
FILTER=""
BRANCH=master
PUSH=false

while [ $# -gt 0 ]; do
  case $1 in
    -s|--sub-project ) SUBPROJECT="$2"; shift; shift;;
    -f|--filter ) FILTER="$2" ; shift; shift;;
    -b|--branch ) BRANCH="$2" ; shift; shift;;
    -p|--push ) PUSH=true   ; shift;;
    * )
     echo "Error: Unknown arg '$1'"
     echo "Usage: $0 -s|--sub-project <sub-project> -f|--filter <filer-file> [-b|--branch <branch>] [-p|--push]"
     exit 1;;
  esac
done

if [ "X${SUBPROJECT}" = "X" -o "X${FILTER}" = "X" ] ; then
  echo "Usage: $0 -s|--sub-project <sub-project> -f|--filter <filer-file> [-b|--branch <branch>] [-p|--push]"
  exit 1
fi

if [ ! -e $FILTER ] ; then
  echo "Error: No such file: $FILTER"
  exit 1
fi

sed -e "s|@PROJECT@|${SUBPROJECT}|;s|@PROJECT_FILTER@|${FILTER}|;s|@BRANCH@|${BRANCH}|" $(dirname $0)/git_filter.cfg > ${SUBPROJECT}.cfg
git clone git@github.com:cms-sw/git_filter
pushd git_filter
  gmake
popd
git clone git@github.com:cms-sw/cmssw
./git_filter/git_filter ${SUBPROJECT}.cfg
cd cmssw
git repack -ad
git remote add ${SUBPROJECT} git@github.com:cms-sw/${SUBPROJECT}
if $PUSH ; then
  git push -f ${SUBPROJECT} ${BRANCH}-${SUBPROJECT}:${BRANCH}
else
  set +x
  echo "Please run the following commands to update the new repository"
  echo "cd cmssw"
  echo "git push -f ${SUBPROJECT} ${BRANCH}-${SUBPROJECT}:${BRANCH}"
fi
