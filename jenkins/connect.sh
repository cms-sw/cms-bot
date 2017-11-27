#!/bin/sh -ex
WORKER_NAME=$1
WORKER_USER=$2
WORKER_NODE=$3
WORKER_DIR=$4

SSH_OPTS="-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
JENKINS_MASTER_ROOT=/build
SCRIPT_DIR=`dirname $0`

if [ $(echo $WORKER_NODE | grep '^aiadm' | wc -l) -gt 0 ] ; then
  AIADM_NODE=$(host aiadm | grep 'has address' | sed 's|.* ||' | head -1 | xargs host | sed 's|.* ||;s|\.*$||')
  WORKER_NODE=$(echo $TARGET | sed "s|^aiadm.*|$AIADM_NODE|")
fi

KPRINCIPAL=$(klist -k ${JENKINS_MASTER_ROOT}/keytabs/${WORKER_USER}.keytab | grep '@' | tail -1 | sed 's|^.* ||')
kinit ${KPRINCIPAL} -k -t ${JENKINS_MASTER_ROOT}/keytabs/${WORKER_USER}.keytab
TARGET="${WORKER_USER}@${WORKER_NODE}"

ssh -n $SSH_OPTS $TARGET mkdir -p $WORKSPACE/tmp
scp -p $SSH_OPTS ${JENKINS_MASTER_ROOT}/slave.jar $TARGET:$WORKSPACE/slave.jar
scp -p $SSH_OPTS ${JENKINS_MASTER_ROOT}/cmsos $TARGET:$WORKSPACE/cmsos
HOST_ARCH=`ssh -n $SSH_OPTS $TARGET cat /proc/cpuinfo | grep vendor_id | sed 's|.*: *||' | tail -1`
HOST_CMS_ARCH=`ssh -n $SSH_OPTS $TARGET sh $WORKSPACE/cmsos`
DOCKER=`ssh -n $SSH_OPTS $TARGET docker --version 2>/dev/null || true`
if [ "X${DOCKER}" != "X" ] ; then DOCKER="docker" ; fi
JENKINS_PREFIX=$(cat ${HOME}/jenkins_prefix)
case $WORKER_NODE in
  *dmwm* ) echo "Skipping auto labels" ;;
  * ) java -jar ${JENKINS_MASTER_ROOT}/jenkins-cli.jar -i ${JENKINS_MASTER_ROOT}/.ssh/id_dsa -s http://localhost:8080/${JENKINS_PREFIX} -remoting groovy ${SCRIPT_DIR}/add-cpu-labels.groovy "${WORKER_NAME}" "${HOST_ARCH}" "${HOST_CMS_ARCH}" "${DOCKER}" ;;
esac
if ! ssh -n $SSH_OPTS $TARGET test -f '~/.jenkins-slave-setup' ; then
  java -jar ${JENKINS_MASTER_ROOT}/jenkins-cli.jar -i ${JENKINS_MASTER_ROOT}/.ssh/id_dsa -s http://localhost:8080/${JENKINS_PREFIX}/ -remoting build 'test-jenkins-host' -p SLAVE_CONNECTION=${TARGET} -p RSYNC_SLAVE_HOME=true -s || true
fi
ssh $SSH_OPTS $TARGET java -jar $WORKSPACE/slave.jar -jar-cache $WORKSPACE/tmp
