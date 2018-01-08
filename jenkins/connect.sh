#!/bin/sh -ex
TARGET=$1 ; shift
JENKINS_SLAVE_NAME=$1; shift
if [ "${JENKINS_SLAVE_NAME}" = "" ] ; then
  echo "Usage: $0 <jenins-slave-name> <remote-user@remote-node> [cleanup]"
  exit 1
fi
export SLAVE_UNIQUE_TARGET=""
export SLAVE_MAX_WORKSPACE_SIZE=""
export JENKINS_SLAVE_NAME
SCRIPT_DIR=`dirname $0`
if [ $(echo $TARGET | grep '@lxplus\|@aiadm' | wc -l) -gt 0 ] ; then
  TARGET_HOST=$(echo $TARGET | sed 's|^.*@||;s|[.].*||')
  export SLAVE_UNIQUE_TARGET="YES"
  case ${TARGET_HOST} in 
    lxplus* ) export SLAVE_MAX_WORKSPACE_SIZE=10;;
  esac
  for ip in $(host $TARGET_HOST | grep 'has address' | sed 's|^.* ||'); do
    NEW_TARGET=$(echo $TARGET | sed "s|@.*|@$ip|")
    ${SCRIPT_DIR}/start-slave.sh "${NEW_TARGET}" "$@" || [ "X$?" = "X99" ] && sleep 5 && continue
    exit 0
  done
  exit 1
fi
${SCRIPT_DIR}/start-slave.sh "${TARGET}" "$@"
