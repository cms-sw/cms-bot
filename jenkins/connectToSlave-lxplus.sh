#!/bin/sh -x
TARGET=$1
WORKER_USER=${2-cmsbuild}
WORKER_DIR=${3-/tmp/$WORKER_USER}
DELETE_SLAVE=${4-yes}
WORKER_JENKINS_NAME=$5
SCRIPT_DIR=`dirname $0`
KTAB=${HOME}/keytabs/${WORKER_USER}.keytab
KPRINCIPAL=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}
SSH_OPTS="-q -o IdentitiesOnly=yes -o PubkeyAuthentication=no -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
TARGET_HOST=$(echo $TARGET | sed 's|^.*@||')
TARGET_USER=$(echo $TARGET | sed 's|@.*$||')
for ip in $(host $TARGET_HOST | grep 'has address' | sed 's|^.* ||'); do
  NEW_TARGET="${TARGET_USER}@$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')"
  ${SCRIPT_DIR}/start-lxplus.sh $NEW_TARGET $WORKER_USER $WORKER_DIR $DELETE_SLAVE $WORKER_JENKINS_NAME || [ "X$?" = "X99" ] && sleep 5 && continue
  exit 0
done
