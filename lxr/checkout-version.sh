#!/bin/bash -e

function set_time()
{
  file=$1
  timestamp=$(git --git-dir=${GITDIR} log -n1 --pretty=format:%at -- $file)
  file_time=$(date -d @${timestamp} '+%Y%m%d%H%M.%S')
  touch -t ${file_time} $file
}

let NUM_PROC=$(nproc)*2
BASE_DIR=$1
tag=$2
[ "X$1" = "X" -o "X$2" = "X" ] && exit 1

GITDIR=${BASE_DIR}/cmssw.git
if [ ! -d "${BASE_DIR}/src/${tag}" ] ; then
  if [ ! -d ${BASE_DIR}/src ] ; then mkdir -p ${BASE_DIR}/src ; fi
  git clone --depth 1 -b $tag file://${GITDIR} ${BASE_DIR}/src/${tag}
  rm -rf ${BASE_DIR}/src/${tag}/.git
fi
cd ${BASE_DIR}/src/${tag}
find . -type f | sed 's|^./||' > ${BASE_DIR}/src/.files
TFILES=$(cat ${BASE_DIR}/src/.files | wc -l)
NFILE=0
for file in $(cat ${BASE_DIR}/src/.files) ; do
  while [ $(jobs -p | wc -l) -ge ${NUM_PROC} ] ; do sleep 0.001 ; done
  let NFILE=${NFILE}+1
  echo "[${NFILE}/${TFILES}] $file"
  set_time $file &
done
wait
rm -f ${BASE_DIR}/src/.files
