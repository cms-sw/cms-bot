#!/bin/bash -e 
BASE_DIR=/data/lxr
GITDIR=${BASE_DIR}/cmssw.git

function update_timestamp()
{
  timestamp=$(git --git-dir=${GITDIR} log -n 1 --pretty=format:%at -- $1)
  file_time=$(date -d @${timestamp} '+%Y%m%d%H%M.%S')
  touch -t ${file_time} $1
}

[ "X$1" = "X" ] && exit 1
tag=$1
cd /data/lxr/src
if [ ! -d "$tag" ] ; then
  git clone ${GITDIR} ${tag}
  cd $tag
  git checkout $tag
  rm -rf .git
else
  cd $tag
fi
COUNT=0
TOTAL=$(find . -type f |wc -l)
for file in $(find . -type f) ; do
  let COUNT=$COUNT+1
  echo $file $COUNT/$TOTAL
  while [ $(jobs | wc -l) -gt 4 ] ; do sleep 0.01 ; done
  update_timestamp $file &
done
wait

