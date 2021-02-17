#!/bin/bash -ex
REQ="${1}"
if [ "${REQ}" = "" -o ! -f "${REQ}" ] ; then
  echo "ERROR: Missing input request file."
  echo "Usage: $0 request-file"
  exit 1
fi
if [ "${BUILD_TAG}${JENKINS_PREFIX}" = "" ] ; then
  echo "Missing BUILD_TAG/JENKINS_PREFIX env.";
  exit 1
fi
SSH_OPT="-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
AIADM_DIR="/afs/cern.ch/user/c/cmsbuild/private/jenkins"
REQ_DIR="${AIADM_DIR}/request"
RES_DIR="${AIADM_DIR}/response"
REQF="REQ-$(basename ${REQ}-${BUILD_TAG}-${JENKINS_PREFIX})"
scp ${SSH_OPT} ${REQ} cmsbuild@lxplus.cern.ch:${REQ_DIR}/${REQF}
WAIT=1800
while [ $WAIT -gt 0 ] ; do
  if ssh ${SSH_OPT} cmsbuild@lxplus.cern.ch "test -f ${RES_DIR}/${REQF}" ; then
    scp ${SSH_OPT} cmsbuild@lxplus.cern.ch:${RES_DIR}/${REQF} ${REQ}.out
    ssh ${SSH_OPT} cmsbuild@lxplus.cern.ch "rm -f ${RES_DIR}/${REQF}" || true
    break
  else
    sleep 60
    let WAIT=$WAIT-60 || true
  fi
done

if [ ! -f "${REQ}.out" ] ; then exit 1; fi
ERR=$(tail -1 ${REQ}.out | grep '^EXIT:' | sed 's|^EXIT:||')
if [ "$ERR" = "" ] ; then ERR=1; fi
sed -e 's|^EXIT:.*||' ${REQ}.out > ${REQ}
rm -f ${REQ}.out
exit $ERR
