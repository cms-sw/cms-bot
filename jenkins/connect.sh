#!/bin/sh -ex
TARGET=$1 ; shift
JENKINS_SLAVE_NAME="${NODE_NAME}"
if [ "$1" = "${NODE_NAME}" ] ; then shift; fi

KTAB=${HOME}/keytabs/$(echo $TARGET | sed 's|@.*||').keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
export SLAVE_TYPE=$(echo $TARGET | sed 's|^.*@||;s|[.].*||')
export KRB5CCNAME=FILE:/tmp/krb5cc_$(id -u)_${KINIT_USER}_${SLAVE_TYPE}
KPRINCIPAL=${KINIT_USER}@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}

export SLAVE_UNIQUE_TARGET=""
export SLAVE_MAX_WORKSPACE_SIZE=""
export JENKINS_SLAVE_NAME
SCRIPT_DIR=$(cd $(dirname $0); /bin/pwd)
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
