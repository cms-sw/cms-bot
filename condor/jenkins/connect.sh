#!/bin/bash -ex
echo $WORKSPACE
SCHEDD_ENV=""
if [ "X$3" != "X" ] ;then
  SCHEDD_ENV="setenv _CONDOR_SCHEDD_HOST $3 && setenv _CONDOR_CREDD_HOST $3 && "
fi
TARGET="${1-cmsbuild@lxplus.cern.ch}"
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
KTAB=${HOME}/keytabs/${REMOTE_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
KPRINCIPAL=${KINIT_USER}@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=90"
ssh $SSH_OPTS ${TARGET} "${SCHEDD_ENV}condor_ssh_to_job -auto-retry $2 'java -jar ${WORKSPACE}/slave.jar -jar-cache ${WORKSPACE}/tmp'"
