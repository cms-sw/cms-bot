#!/bin/bash -ex
echo $WORKSPACE
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=90"
SCHEDD_ENV=""
TARGET="${1-cmsbuild@lxplus.cern.ch}"
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
if [ "X$3" != "X" ] ; then
  if [ $(ssh -n $SSH_OPTS ${TARGET} echo \$SHELL 2>&1 | grep /tcsh |wc -l) -gt 0 ] ; then
    SCHEDD_ENV="setenv _CONDOR_SCHEDD_HOST $3 && setenv _CONDOR_CREDD_HOST $3 && setenv SINGULARITY_BINDPATH /pool && "
  else
    SCHEDD_ENV="export _CONDOR_SCHEDD_HOST=$3 && export _CONDOR_CREDD_HOST=$3 && export SINGULARITY_BINDPATH=/pool && "
    K5COPY=true
  fi
fi
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
KTAB=${HOME}/keytabs/${REMOTE_USER}.keytab
if [ ! -f $KTAB ] ; then KTAB=${HOME}/keytabs/cmsbld.keytab ; fi
KINIT_USER=$(klist -k -t -K ${KTAB} | sed  's|@CERN.CH.*||;s|.* ||' | tail -1)
KPRINCIPAL=${KINIT_USER}@CERN.CH
export KRB5CCNAME=FILE:/tmp/krb5cc_$(id -u)_${KINIT_USER}_${2}
kinit ${KPRINCIPAL} -k -t ${KTAB}
if $K5COPY ; then
  ssh $SSH_OPTS ${TARGET} "${SCHEDD_ENV}K5FILE=\$(klist | grep 'FILE:' | sed 's|.*FILE:||') && rsync -v -e 'condor_ssh_to_job' \$K5FILE $2:~/${REMOTE_USER}.cc"
fi
ssh $SSH_OPTS ${TARGET} "${SCHEDD_ENV}condor_ssh_to_job -auto-retry $2 'java -jar ${WORKSPACE}/slave.jar -jar-cache ${WORKSPACE}/tmp'"
