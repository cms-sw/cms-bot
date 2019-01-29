#!/bin/bash -e 
BASE_DIR=/data/lxr
GITDIR=${BASE_DIR}/cmssw.git

[ "X$1" = "X" ] && exit 1
tag=$1
cd ${BASE_DIR}/src
if [ ! -d "$tag" ] ; then
  git clone ${GITDIR} ${tag}
  cd $tag
  git checkout $tag
  rm -rf .git
else
  cd $tag
fi
for file in $(find . -type f | sed 's|^./||') ; do
  timestamp=$(git --git-dir=${GITDIR} log -n1 --pretty=format:%at -- $file)
  file_time=$(date -d @${timestamp} '+%Y%m%d%H%M.%S')
  echo "$file $file_time"
  touch -t ${file_time} $file
done
