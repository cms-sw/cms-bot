#!/bin/bash -ex
SCRIPT_DIR=$(cd $(dirname $0); /bin/pwd -P)
PROJECT="cmssw"
SUBPROJECT="Stitched"
FILTER=""
BRANCH=master
PUSH=false
TAG=false

while [ $# -gt 0 ]; do
  case $1 in
    -P|--project )     PROJECT="$2";    shift; shift;;
    -s|--sub-project ) SUBPROJECT="$2"; shift; shift;;
    -f|--filter ) FILTER="$2" ; shift; shift;;
    -b|--branch ) BRANCH="$2" ; shift; shift;;
    -p|--push )   PUSH=true   ; shift;;
    * )
     echo "Error: Unknown arg '$1'"
     echo "Usage: $0 -s|--sub-project <sub-project e.g. Stitched> [-P|--project <project e.g cmssw>] [-f|--filter <filer-file>] [-b|--branch <branch|tag>] [-p|--push]"
     exit 1;;
  esac
done

if [ "X${SUBPROJECT}" = "X" -o "X${PROJECT}" = "X" ] ; then
  echo "Usage: $0 -s|--sub-project <sub-project e.g. Stitched> [-P|--project <project e.g cmssw>] [-f|--filter <filer-file>] [-b|--branch <branch|tag>] [-p|--push]"
  exit 1
fi

if [ "$(echo ${SUBPROJECT} | tr '[A-Z]' '[a-z]')" = "$(echo ${PROJECT} | tr '[A-Z]' '[a-z]')" ] ; then
  echo "ERROR: Project and sub-project can not be same."
  exit 1
fi


if [ "$FILTER" = "" ] ; then FILTER="${SCRIPT_DIR}/${SUBPROJECT}.filter" ; fi
if [ ! -e $FILTER ] ; then
  echo "Error: No such file: $FILTER"
  exit 1
fi

if [ ! -d git_filter ] ; then
  git clone git@github.com:cms-sw/git_filter
  pushd git_filter
    gmake
  popd
fi

if [ ! -d ${PROJECT} ] ; then
  git clone git@github.com:cms-sw/${PROJECT}
fi
NEW_BRANCH=${BRANCH}
pushd ${PROJECT}
  git clean -fdx
  git fetch --force origin
  if [ $(git tag | grep "^${BRANCH}$" | wc -l ) -eq 1 ] ; then TAG=true; fi
  if $TAG ; then
    BRANCH="${SUBPROJECT}-${BRANCH}"
    git branch -D ${BRANCH} || true
    git checkout -b ${BRANCH} ${NEW_BRANCH}
  else
    git checkout ${BRANCH} || true
  fi
  LOCAL_BRANCH=${BRANCH}-${SUBPROJECT}
  git branch -D ${LOCAL_BRANCH} ||  true
popd

sed -e "s|@PROJECT@|${SUBPROJECT}|;s|@PROJECT_FILTER@|${FILTER}|;s|@BRANCH@|${BRANCH}|" ${SCRIPT_DIR}/git_filter.cfg > ${SUBPROJECT}.cfg
./git_filter/git_filter ${SUBPROJECT}.cfg

cd ${PROJECT}
git checkout ${LOCAL_BRANCH}
if $TAG ; then
  LOCAL_BRANCH=TAG_${SUBPROJECT}_${NEW_BRANCH}
  git tag -d ${NEW_BRANCH}
  git tag -d ${LOCAL_BRANCH} || true
  git tag ${LOCAL_BRANCH}
fi

git repack -ad
git remote add ${SUBPROJECT} git@github.com:cms-sw/${SUBPROJECT} || true
if $PUSH ; then
  git push -f ${SUBPROJECT} ${LOCAL_BRANCH}:${NEW_BRANCH}
else
  set +x
  echo "Please run the following commands to update the new repository"
  echo "cd ${PROJECT}"
  echo "git push -f ${SUBPROJECT} ${LOCAL_BRANCH}:${NEW_BRANCH}"
fi
