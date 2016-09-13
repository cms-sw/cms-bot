#!/bin/sh -x
TARGET=$1
WORKER_USER=${2-cmsbuild}
WORKER_DIR=${3-/build1/cmsbuild}
DELETE_SLAVE=${4-yes}
WORKER_JENKINS_NAME=$5

kinit $WORKER_USER@CERN.CH -k -t /build/cmsbuild/jenkins/$WORKER_USER.keytab
aklog
klist

SSH_OPTS="-o IdentitiesOnly=yes -o PubkeyAuthentication=no -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
max_loop=30
SCRIPT_DIR=`dirname $0`
while [ true  ] ; do
  max_loop=`expr ${max_loop} - 1`
  [ "X${max_loop}" = "X0" ] && exit 0
  NEW_TARGET="${WORKER_USER}@`ssh -f $SSH_OPTS -n $TARGET hostname`"
  if [ "${NEW_TARGET}" = "${WORKER_USER}@" ] ; then sleep 10; continue ; fi
  ${SCRIPT_DIR}/start-lxplus.sh $NEW_TARGET $WORKER_USER $WORKER_DIR $DELETE_SLAVE $WORKER_JENKINS_NAME || [ "X$?" = "X99" ] && sleep 30 && continue
  exit 0
done
