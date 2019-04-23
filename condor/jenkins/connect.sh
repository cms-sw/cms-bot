#!/bin/bash -ex
export _CONDOR_SCHEDD_HOST=bigbird15.cern.ch
export _CONDOR_CREDD_HOST=bigbird15.cern.ch
echo $WORKSPACE
TARGET="${1-cmsbuild@lxplus.cern.ch}"
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
KTAB=${HOME}/keytabs/${REMOTE_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
KPRINCIPAL=${KINIT_USER}@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
ssh $SSH_OPTS ${TARGET} "export _CONDOR_SCHEDD_HOST=bigbird15.cern.ch && export _CONDOR_CREDD_HOST=bigbird15.cern.ch && condor_ssh_to_job -auto-retry $2 'java -jar ${WORKSPACE}/slave.jar -jar-cache ${WORKSPACE}/tmp'"
