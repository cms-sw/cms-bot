#!/bin/bash -ex
#usage $0 <OS> <connection-string> e.g. connect.sh el8 username@host.domain
OS=$1
TARGET=$2

# Values from get_slot.sh
USER=cmsbuild
SESSION=$OS
SLURM_ACCOUNT=project_462000245
SCRATCH=/scratch/$SLURM_ACCOUNT/$USER/$SESSION

KTAB=${HOME}/keytabs/$(echo $TARGET | sed 's|@.*||').keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
export KRB5CCNAME=FILE:/tmp/krb5cc_${USER}_${NODE_NAME}
kinit $USER@CERN.CH -k -t ${KTAB}
klist || true

KRB5_FILENAME=$(echo $KRB5CCNAME | sed 's|^FILE:||')
scp -p $SSH_OPTS ${KRB5_FILENAME} $TARGET:$SCRATCH

echo "Launching LUMI node... for ${OS} using ${TARGET}"
JENKINS_VERSION=$(jenkins --version)
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

scp $SSH_OPTS /var/lib/jenkins/slave.jar ${TARGET}:~/cmsbuild/slave-${NODE_NAME}.jar
ssh $SSH_OPTS ${TARGET} "~/cmsbuild/cms-bot/lumi/get_slot.sh ${OS} ${USER} ~/cmsbuild/slave-${NODE_NAME}.jar ${SLURM_ACCOUNT}"
