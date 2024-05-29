#!/bin/bash -ex
#usage $0 <OS> <connection-string> e.g. connect.sh el8 username@host.domain
OS=$1
CONNECTION=$2

echo "Launching LUMI node... for ${OS} using ${CONNECTION}"
JENKINS_VERSION=$(jenkins --version)
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

CUR_DIR=$(dirname $0)
LUMI_DIR=$(basename $CUR_DIR)
#every ssh connect before the last one should use -n option
ssh -n $SSH_OPTS ${CONNECTION} "mkdir -p ~/cmsbuild"
scp $SSH_OPTS -r ${CUR_DIR} ${CONNECTION}:~/cmsbuild/
scp $SSH_OPTS /var/lib/jenkins/slave.jar ${CONNECTION}:~/cmsbuild/slave-${JENKINS_VERSION}.jar
ssh $SSH_OPTS ${CONNECTION} "~/cmsbuild/${LUMI_DIR}/get_slot.sh ${OS} ~/cmsbuild/slave-${JENKINS_VERSION}.jar"
