#!/bin/bash -x
#$0 PR_NUM pr-user/user-branch cms-user/cms-repo dest-branch
PR_NUM=$1
PR_USER=`echo $2 | sed 's|/.*||'`
PR_BRANCH=`echo $2 | sed 's|.*/||'`
REPO_NAME=`echo $3 | sed 's|.*/||'`
CMS_USER=`echo $3 | sed 's|/.*||'`
REPO_DES_BRANCH=$4

REPO_REF=""
if [ ! -d "${REPO_NAME}" ] ; then
  if [ -e /afs/cern.ch/cms/git-cmssw-mirror/${REPO_NAME}.git ] ; then
    REPO_REF="--reference /afs/cern.ch/cms/git-cmssw-mirror/${REPO_NAME}.git"
  fi
  git clone ${REPO_REF} git@github.com:${CMS_USER}/${REPO_NAME} ${REPO_NAME}
fi
cd ${REPO_NAME}
git clean -fdx
git checkout ${REPO_DES_BRANCH}
git reset --hard origin/$REPO_DES_BRANCH
git clean -fdx
git pull --rebase

CUR_BRANCH=`git branch | grep '^*' | sed 's|.* ||'`
if [ "X${CUR_BRANCH}" != "X${REPO_DES_BRANCH}" ] ; then
  echo "Unable to checkout ${REPO_DES_BRANCH} branch"
  exit 1
fi
NEW_BRANCH=port-${PR_NUM}-`echo ${REPO_DES_BRANCH} | tr / -`
git remote rm user || true
git remote add user git@github.com:${PR_USER}/${REPO_NAME}.git
git branch -D ${NEW_BRANCH} || true
git branch -D ${PR_BRANCH} || true
git fetch user ${PR_BRANCH}:${PR_BRANCH}
git checkout -b ${NEW_BRANCH}

