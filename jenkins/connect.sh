#!/bin/sh -ex
TARGET=$1 ; shift
if [ "$1" != "${NODE_NAME}" ] ; then exec $0 "${TARGET}" "${NODE_NAME}" "$@"; fi
opts="$0 +${TARGET} +${NODE_NAME} +"
if [ $(pgrep -f "$opts" | wc -l) -gt 2 ] ; then
  pgrep -af "$opts" | grep -v "^$$ "
  echo "WARNING: There is already a process trying to connect. please wait for that process to finish first"
  exit 0
else
  shift
fi

KTAB=${HOME}/keytabs/$(echo $TARGET | sed 's|@.*||').keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
export SLAVE_TYPE=$(echo $TARGET | sed 's|^.*@||;s|[.].*||')
export KRB5CCNAME=FILE:/tmp/krb5cc_$(id -u)_${KINIT_USER}_${SLAVE_TYPE}
KPRINCIPAL=${KINIT_USER}@CERN.CH
kinit ${KPRINCIPAL} -k -t ${KTAB}
klist || true
export SLAVE_UNIQUE_TARGET=""
export SLAVE_MAX_WORKSPACE_SIZE=""
SCRIPT_DIR=$(cd $(dirname $0); /bin/pwd)
BLACKLIST_DIR="${HOME}/workspace/cache/blacklist"

if [ $(echo $SLAVE_TYPE | grep '^lxplus\|^aiadm' | wc -l) -gt 0 ] ; then
  export SLAVE_UNIQUE_TARGET="YES"
  case ${SLAVE_TYPE} in 
    lxplus* ) export SLAVE_MAX_WORKSPACE_SIZE=10;;
  esac
  for ip in $(host $SLAVE_TYPE | grep 'has address' | sed 's|^.* ||'); do
    hname=$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')
    if [ $(grep $(echo "${hname}" | cut -d "." -f 1) ${SCRIPT_DIR}/blacklist-lxplus.txt | wc -l) -gt 0 ] ; then continue ; fi
    if [ -e ${BLACKLIST_DIR}/${hname} ] ; then continue ; fi
    NEW_TARGET=$(echo $TARGET | sed "s|@.*|@$hname|")
    ${SCRIPT_DIR}/start-slave.sh "${NEW_TARGET}" "$@" || [ "X$?" = "X99" ] && sleep 5 && continue
    exit 0
  done
  exit 1
fi
${SCRIPT_DIR}/start-slave.sh "${TARGET}" "$@"
