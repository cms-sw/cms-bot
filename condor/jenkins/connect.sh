#!/bin/bash -ex
echo $WORKSPACE
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=90"
SCHEDD_ENV=""
TARGET="${1-cmsbuild@lxplus.cern.ch}"
LABELS=$(grep '<label>' ${HOME}/nodes/${NODE_NAME}/config.xml | tr '<>' ' ')
GRID_ID=$(echo "${LABELS}"     | grep -o "gridid-\w*\.0"                  | awk 'BEGIN {FS="-";} { print $2 }')
SCHEDD_NAME=$(echo "${LABELS}" | grep -o "schedulername-\w*\.*\w*\.*\w*"  | awk 'BEGIN {FS="-";} { print $2 }')
JAVA="java"
if [ "$(echo ${LABELS} | grep -o 'java-17')" = "java-17" ] ; then
  JAVA="/etc/alternatives/jre_17/bin/java"
elif [ "$(echo ${LABELS} | grep -o 'java-11')" = "java-11" ] ; then
  JAVA="/etc/alternatives/jre_11/bin/java"
fi

export SLAVE_TYPE=$(echo $TARGET | sed 's|^.*@||;s|[.].*||')
if [ $(echo $SLAVE_TYPE | grep '^lxplus\|^aiadm' | wc -l) -gt 0 ] ; then
  for ip in $(host $SLAVE_TYPE | grep 'has address' | sed 's|^.* ||'); do
    hname=$(host $ip | grep 'domain name' | sed 's|^.* ||;s|\.$||')
    NEW_TARGET=$(echo $TARGET | sed "s|@.*|@$hname|")
    if ssh -n $SSH_OPTS $NEW_TARGET 'grep -q "Puppet environment: production" /etc/motd' ; then
      TARGET="${NEW_TARGET}"
      break
    fi
  done
fi
K5COPY=false
if [ "X$SCHEDD_NAME" != "X" ] ; then
  if [ $(ssh -n $SSH_OPTS ${TARGET} echo \$SHELL 2>&1 | grep /tcsh |wc -l) -gt 0 ] ; then
    SCHEDD_ENV="setenv _CONDOR_SCHEDD_HOST $SCHEDD_NAME && setenv _CONDOR_CREDD_HOST $SCHEDD_NAME && setenv SINGULARITY_BINDPATH /pool && kinit -R && "
  else
    SCHEDD_ENV="export _CONDOR_SCHEDD_HOST=$SCHEDD_NAME && export _CONDOR_CREDD_HOST=$SCHEDD_NAME && export SINGULARITY_BINDPATH=/pool && kinit -R && "
    K5COPY=true
  fi
fi
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
KTAB=${HOME}/keytabs/${REMOTE_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
KPRINCIPAL=${KINIT_USER}@CERN.CH
export KRB5CCNAME=FILE:/tmp/krb5cc_$(id -u)_${KINIT_USER}_${GRID_ID}
kinit ${KPRINCIPAL} -k -t ${KTAB}
if $K5COPY ; then
  ssh -n $SSH_OPTS ${TARGET} "${SCHEDD_ENV}K5FILE=\$(klist | grep 'FILE:' | sed 's|.*FILE:||') && rsync -v -e 'condor_ssh_to_job' \$K5FILE $GRID_ID:~/${REMOTE_USER}.cc"
fi
JAVA_OPTS="-Djdk.reflect.useDirectMethodHandle=false   --add-opens java.base/java.lang=ALL-UNNAMED   --add-opens java.base/java.lang.reflect=ALL-UNNAMED"
ssh $SSH_OPTS ${TARGET} "${SCHEDD_ENV}condor_ssh_to_job -auto-retry $GRID_ID '${JAVA} ${JAVA_OPTS} -jar ${WORKSPACE}/slave.jar -jar-cache ${WORKSPACE}/tmp'" || true
ssh $SSH_OPTS ${TARGET} "${SCHEDD_ENV}condor_ssh_to_job -auto-retry $GRID_ID 'rm -rf .condor_ssh_to_job_*'"
