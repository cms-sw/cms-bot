#!/bin/bash -e
THISDIR=$(dirname $0)
REQ="${1}/request"
RES="${1}/response"

LOCK="${REQ}/lock"
if [ -f ${LOCK} ] ; then
  let age=$(date +%s)-$(stat -c %Y ${LOCK})
  if [ $age -gt 600 ] ; then
    rm -f ${LOCK}
  else
    exit 0
  fi
fi
XID="$(hostname -s):$$:"
echo "${XID}" > ${LOCK}
sleep 5
let STIME=$(date +%s)+7200
echo "$(date): ${XID} Started via ${2}" >> ${REQ}/status
while [ $(date +%s) -lt ${STIME} ] ; do
  if [ $((grep "^${XID}" ${LOCK} 2>/dev/null || true) | wc -l) -eq 0 ] ; then
    echo "$(date): ${XID} Aborted" >> ${REQ}/status
    exit 0
  fi
  if [ -e ${REQ}/stop ] ; then
    rm -f ${REQ}/stop
    break
  fi
  touch ${LOCK}
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
      echo "$(date): ${rf}: $ERR" >> ${REQ}/status
      echo "EXIT:$ERR" >> ${RES}/${rf}.tmp
      mv ${RES}/${rf}.tmp ${RES}/${rf}
    else
      rm -rf $r
    fi
    touch ${LOCK}
  done
  sleep 10
done
touch ${REQ}/status ${LOCK}
find ${REQ} -mindepth 1 -maxdepth 1 -mmin +59 | xargs  --no-run-if-empty rm -rf 
find ${RES} -mindepth 1 -maxdepth 1 -mmin +59 | xargs  --no-run-if-empty rm -rf
echo "$(date): ${XID} Stopped" >> ${REQ}/status
rm -f ${LOCK} || true
