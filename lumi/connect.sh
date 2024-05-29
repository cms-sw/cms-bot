#!/bin/bash -e

echo "Launching LUMI node..."

JENKINS_VERSION=$(jenkins --version)
OS=$1

SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

LUMI_BASE_DIR="cmsbuild/jenkins_lumi"

scp -r $SSH_OPTS $(dirname $0)/* andbocci@lumi.csc.fi:~/$LUMI_BASE_DIR
scp $SSH_OPTS /var/lib/jenkins/slave.jar andbocci@lumi.csc.fi:~/$LUMI_BASE_DIR/slave-${JENKINS_VERSION}.jar
ssh $SSH_OPTS andbocci@lumi.csc.fi ./$LUMI_BASE_DIR/get_slot.sh ${OS} /users/andbocci/$LUMI_BASE_DIR/slave-${JENKINS_VERSION}.jar
