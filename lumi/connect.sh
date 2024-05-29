#!/bin/bash -ex
#usage $0 <OS> <connection-string> e.g. connect.sh el8 username@host.domain
OS=$1
CONNECTION=$2

echo "Launching LUMI node... for ${OS} using ${CONNECTION}"
JENKINS_VERSION=$(jenkins --version)
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

scp $SSH_OPTS /var/lib/jenkins/slave.jar ${CONNECTION}:~/cmsbuild/slave-${NODE_NAME}.jar
ssh $SSH_OPTS ${CONNECTION} "~/cmsbuild/cms-bot/lumi/get_slot.sh ${OS} ~/cmsbuild/slave-${NODE_NAME}.jar"
