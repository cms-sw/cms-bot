#!/bin/sh -ex
TARGET=$1
CLEANUP_WORKSPACE=$2
SSH_OPTS="-q -o IdentitiesOnly=yes -o PubkeyAuthentication=no -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

#Check unique slave conenction
if [ "${SLAVE_UNIQUE_TARGET}" = "YES" ] ; then
  if [ `pgrep -f " ${TARGET} " | grep -v "$$" | wc -l` -gt 1 ] ; then
    exit 99
  fi
fi

#Check slave workspace size in GB
if [ "${SLAVE_MAX_WORKSPACE_SIZE}" != "" ] ; then
  TMP_SPACE=`ssh -f $SSH_OPTS -n $TARGET df -k $WORKSPACE | tail -1 | sed 's|^/[^ ]*  *||' | awk '{print $3}'`
  if [ `echo "$TMP_SPACE/(1024*1024)" | bc` -lt $SLAVE_MAX_WORKSPACE_SIZE ] ; then exit 99 ; fi
fi

WORKER_USER=$(echo $TARGET | sed 's|@.*||')
SCRIPT_DIR=`dirname $0`
KTAB=${HOME}/keytabs/${WORKER_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KPRINCIPAL=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}
if [ "${CLEANUP_WORKSPACE}" = "cleanup" ] ; then ssh -n $SSH_OPTS $TARGET rm -rf $WORKSPACE ; fi
ssh -n $SSH_OPTS $TARGET mkdir -p $WORKSPACE/tmp $WORKSPACE/workspace
ssh -n $SSH_OPTS $TARGET rm -f $WORKSPACE/cmsos $WORKSPACE/slave.jar
scp -p $SSH_OPTS ${HOME}/slave.jar $TARGET:$WORKSPACE/slave.jar
scp -p $SSH_OPTS ${HOME}/cmsos $TARGET:$WORKSPACE/cmsos
HOST_ARCH=`ssh -n $SSH_OPTS $TARGET cat /proc/cpuinfo | grep vendor_id | sed 's|.*: *||' | tail -1`
HOST_CMS_ARCH=`ssh -n $SSH_OPTS $TARGET sh $WORKSPACE/cmsos`
DOCKER=`ssh -n $SSH_OPTS $TARGET docker --version 2>/dev/null || true`
if [ "X${DOCKER}" != "X" ] ; then DOCKER="docker" ; fi
JENKINS_CLI_OPTS="-jar ${HOME}/jenkins-cli.jar -i ${JENKINS_MASTER_ROOT}/.ssh/id_dsa -s http://localhost:8080/$(cat ${HOME}/jenkins_prefix) -remoting"
case $TARGET in
  *dmwm* ) echo "Skipping auto labels" ;;
  *lxplus* ) java ${JENKINS_CLI_OPTS} groovy $SCRIPT_DIR/lxplus-labels.groovy "${JENKINS_SLAVE_NAME}" "$HOST_ARCH" $DELETE_SLAVE `echo $TARGET | sed 's|.*@||'` $CMS_ARCH
  * )        java ${JENKINS_CLI_OPTS} groovy ${SCRIPT_DIR}/add-cpu-labels.groovy "${JENKINS_SLAVE_NAME}" "$HOST_ARCH" "$HOST_CMS_ARCH" "${DOCKER}" ;;
esac
if ! ssh -n $SSH_OPTS $TARGET test -f '~/.jenkins-slave-setup' ; then
  java ${JENKINS_CLI_OPTS} build 'jenkins-test-slave' -p SLAVE_CONNECTION=${TARGET} -p RSYNC_SLAVE_HOME=true -s || true
fi
ssh $SSH_OPTS $TARGET java -jar $WORKSPACE/slave.jar -jar-cache $WORKSPACE/tmp
