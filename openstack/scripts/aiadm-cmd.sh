#!/bin/bash -ex
AIADM_DIR="$1"
REQ="$2"
if [ "${REQ}" = "" -o ! -f "${REQ}" ] ; then
  echo "ERROR: Missing input request file."
  echo "Usage: $0 request-file"
  exit 1
fi
if [ "${BUILD_TAG}${JENKINS_PREFIX}" = "" ] ; then
  echo "Missing BUILD_TAG/JENKINS_PREFIX env.";
  exit 1
fi
REMOTE_ADD="cmsbuild@lxplus.cern.ch"
SSH_OPT="-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
REQ_DIR="${AIADM_DIR}/request"
RES_DIR="${AIADM_DIR}/response"
REQF="REQ-$(basename ${REQ}-${BUILD_TAG}-${JENKINS_PREFIX})"
LOCAL=false
if [ -d ${REQ_DIR} ] ; then
  LOCAL=true
  cp ${REQ} ${REQ_DIR}/tmp-${REQF}
  mv ${REQ_DIR}/tmp-${REQF} ${REQ_DIR}/${REQF}
else
  scp ${SSH_OPT} ${REQ} ${REMOTE_ADD}:${REQ_DIR}/tmp-${REQF}
  ssh ${SSH_OPT} ${REMOTE_ADD} "mv ${REQ_DIR}/tmp-${REQF} ${REQ_DIR}/${REQF}"
fi
WAIT=1800
while [ $WAIT -gt 0 ] ; do
  if $LOCAL ; then
    if [ -f ${RES_DIR}/${REQF} ] ; then
      cp ${RES_DIR}/${REQF} ${REQ}.out
      rm -f ${RES_DIR}/${REQF}
      break
    fi
  else
    if ssh ${SSH_OPT} ${REMOTE_ADD} "test -f ${RES_DIR}/${REQF}" ; then
      scp ${SSH_OPT}  ${REMOTE_ADD}:${RES_DIR}/${REQF} ${REQ}.out
      ssh ${SSH_OPT}  ${REMOTE_ADD} "rm -f ${RES_DIR}/${REQF}" || true
      break
    fi
  fi
  sleep 30
  let WAIT=$WAIT-30 || true
done

if [ ! -f "${REQ}.out" ] ; then exit 1; fi
ERR=$(tail -1 ${REQ}.out | grep '^EXIT:' | sed 's|^EXIT:||')
if [ "$ERR" = "" ] ; then ERR=1; fi
sed -e 's|^EXIT:.*||' ${REQ}.out > ${REQ}
rm -f ${REQ}.out
cat ${REQ}
exit $ERR
