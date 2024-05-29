#!/bin/bash -e

echo "Launching LUMI node..."

JENKINS_VERSION=$(jenkins --version)
OS=$1

SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

CUR_DIR=$(dirname $0)
LUMI_DIR=$(basename $CUR_DIR)
ssh $SSH_OPTS andbocci@lumi.csc.fi "mkdir -p ~/cmsbuild"
scp $SSH_OPTS -r ${CUR_DIR} andbocci@lumi.csc.fi:~/cmsbuild/
scp $SSH_OPTS /var/lib/jenkins/slave.jar andbocci@lumi.csc.fi:~/cmsbuild/slave-${JENKINS_VERSION}.jar
ssh $SSH_OPTS andbocci@lumi.csc.fi "~/cmsbuild/${LUMI_DIR}/get_slot.sh ${OS} ~/cmsbuild/slave-${JENKINS_VERSION}.jar"
