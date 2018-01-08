#!/bin/sh -ex
TARGET=$1 ; shift
JENKINS_SLAVE_NAME=$1; shift
if [ "${JENKINS_SLAVE_NAME}" = "" ] ; then
  set +x
  JENKINS_NODES=$(grep "${TARGET}" ${HOME}/nodes/*/config.xml | sed 's|/config.xml:.*||;s|.*/||' | sort | uniq)
  set -x
  if [ $(echo $JENKINS_NODES | wc -l) -ne 1 ] ; then
    echo "Usage: $0 <jenins-slave-name> <remote-user@remote-node> [cleanup]"
    exit 1
  fi
  JENKINS_SLAVE_NAME=${JENKINS_NODES}
fi

KTAB=${HOME}/keytabs/$(echo $TARGET | sed 's|@.*||').keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KPRINCIPAL=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}

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
