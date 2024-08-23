#!/bin/bash -ex
TARGET=$1
USER=cmsbuild
SCRATCH=/home/smmuzaffar/cmsbld/${NODE_NAME}

KTAB=${HOME}/keytabs/$(echo $TARGET | sed 's|@.*||').keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
export KRB5CCNAME=FILE:/tmp/krb5cc_${USER}_${NODE_NAME}
kinit $USER@CERN.CH -k -t ${KTAB}
klist || true
KRB5_FILENAME=$(echo $KRB5CCNAME | sed 's|^FILE:||')

SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
SSH_CMD="ssh -p 2223 ${SSH_OPTS}"
SCP_CMD="scp -P 2223 ${SSH_OPTS}"

$SSH_CMD -n $TARGET "mkdir -p $SCRATCH"
$SCP_CMD ${KRB5_FILENAME} $TARGET:${SCRATCH}/krb5cc_${USER}
$SCP_CMD /var/lib/jenkins/slave.jar $TARGET:${SCRATCH}/slave.jar
$SSH_CMD $TARGET "ssh milkv-2 java \
  --add-opens java.base/java.lang=ALL-UNNAMED \
  --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
  -jar ${SCRATCH}/slave.jar -jar-cache $WORKSPACE/tmp"
