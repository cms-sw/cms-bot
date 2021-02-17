#!/bin/bash -e
THISDIR=$(dirname $0)
REQ="${1}/request"
RES="${1}/response"

touch ${REQ}/status
for r in $(ls -d ${REQ}/REQ-* 2>/dev/null | grep '/REQ-[a-zA-Z][a-zA-Z0-9_-]*$' || true) ; do
  if [ -f $r ] ; then
    rf=$(basename $r)
    ERR=0
    cmd=$(echo $rf | sed 's|^REQ-||;s|-.*||')
    cmd2run=${THISDIR}/cmds/${cmd}.sh
    if [ -f ${cmd2run} ] ; then
      ${cmd2run} $r > ${RES}/${rf}.tmp 2>&1 || ERR=1
    else
      echo "ERROR: Invalid request $cmd" > ${RES}/${rf}.tmp
      ERR=1
    fi
    rm -rf $r
    echo "EXIT:$ERR" >> ${RES}/${rf}.tmp
    mv ${RES}/${rf}.tmp ${RES}/${rf}
  else
    rm -rf $r
  fi
done

find ${REQ} -mindepth 1 -maxdepth 1 -mmin +59 | xargs  --no-run-if-empty rm -rf 
find ${RES} -mindepth 1 -maxdepth 1 -mmin +59 | xargs  --no-run-if-empty rm -rf
