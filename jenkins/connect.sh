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
export SLAVE_TYPE=$(echo $TARGET | sed 's|^.*@||;s|[.].*||')
if [ $(echo $SLAVE_TYPE | grep '^lxplus\|^aiadm' | wc -l) -gt 0 ] ; then
  export SLAVE_UNIQUE_TARGET="YES"
  case ${SLAVE_TYPE} in 
    lxplus* ) export SLAVE_MAX_WORKSPACE_SIZE=10;;
  esac
  for ip in $(host $SLAVE_TYPE | grep 'has address' | sed 's|^.* ||'); do
    hname=$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')
    NEW_TARGET=$(echo $TARGET | sed "s|@.*|@$hname|")
    ${SCRIPT_DIR}/start-slave.sh "${NEW_TARGET}" "$@" || [ "X$?" = "X99" ] && sleep 5 && continue
    exit 0
  done
  exit 1
fi
${SCRIPT_DIR}/start-slave.sh "${TARGET}" "$@"
