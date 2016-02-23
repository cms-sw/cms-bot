#!/bin/sh -ex
TARGET=$1
WORKER_USER=${2-cmsbuild}

kinit $WORKER_USER@CERN.CH -k -t /build/cmsbuild/jenkins/$WORKER_USER.keytab
SSH_OPTS="-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"
ssh -f $SSH_OPTS $TARGET mkdir -p /build1/cmsbuild
ssh -f $SSH_OPTS $TARGET ls -la /build1/cmsbuild
ssh -f $SSH_OPTS $TARGET curl -k -o/build1/cmsbuild/slave.jar https://cmssdt.cern.ch/SDT/slave.jar
sleep 1
ssh $SSH_OPTS $TARGET java -jar /build1/cmsbuild/slave.jar
