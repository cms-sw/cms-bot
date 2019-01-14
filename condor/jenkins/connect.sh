#!/bin/bash -ex
echo $WORKSPACE
TARGET="${1-cmsbuild@lxplus.cern.ch}"
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
KTAB=${HOME}/keytabs/${REMOTE_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
kinit ${KPRINCIPAL} -k -t ${KTAB}
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
ssh $SSH_OPTS ${TARGET} "condor_ssh_to_job -auto-retry $2 'java -jar ${WORKSPACE}/slave.jar -jar-cache ${WORKSPACE}/tmp'"
