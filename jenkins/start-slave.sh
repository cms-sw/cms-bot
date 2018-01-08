#!/bin/sh -ex
TARGET=$1
CLEANUP_WORKSPACE=$2
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

#Check unique slave conenction
if [ "${SLAVE_UNIQUE_TARGET}" = "YES" ] ; then
  if [ `pgrep -f " ${TARGET} " | grep -v "$$" | wc -l` -gt 1 ] ; then
    exit 99
  fi
fi

#Check slave workspace size in GB
if [ "${SLAVE_MAX_WORKSPACE_SIZE}" != "" ] ; then
  TMP_SPACE=$(ssh -f $SSH_OPTS -n $TARGET df -k $(dirname $WORKSPACE) | tail -1 | sed 's|^/[^ ]*  *||' | awk '{print $3}')
  if [ $(echo "$TMP_SPACE/(1024*1024)" | bc) -lt $SLAVE_MAX_WORKSPACE_SIZE ] ; then exit 99 ; fi
fi

SCRIPT_DIR=`dirname $0`
if [ "${CLEANUP_WORKSPACE}" = "cleanup" ] ; then ssh -n $SSH_OPTS $TARGET rm -rf $WORKSPACE ; fi
ssh -n $SSH_OPTS $TARGET mkdir -p $WORKSPACE/tmp $WORKSPACE/workspace
ssh -n $SSH_OPTS $TARGET rm -f $WORKSPACE/cmsos $WORKSPACE/slave.jar
scp -p $SSH_OPTS ${HOME}/slave.jar $TARGET:$WORKSPACE/slave.jar
scp -p $SSH_OPTS ${HOME}/cmsos $TARGET:$WORKSPACE/cmsos
HOST_ARCH=$(ssh -n $SSH_OPTS $TARGET cat /proc/cpuinfo | grep vendor_id | sed 's|.*: *||' | tail -1)
HOST_CMS_ARCH=$(ssh -n $SSH_OPTS $TARGET sh $WORKSPACE/cmsos)
JENKINS_CLI_OPTS="-jar ${HOME}/jenkins-cli.jar -i ${HOME}/.ssh/id_dsa -s http://localhost:8080/$(cat ${HOME}/jenkins_prefix) -remoting"
case ${SLAVE_TYPE} in
  *dmwm* ) echo "Skipping auto labels" ;;
  *lxplus* )
    case ${HOST_CMS_ARCH} in 
      slc6_*) lxplus_type="lxplus6";;
      slc7_*) lxplus_type="lxplus7";;
    esac
    if [ "${CLEANUP_WORKSPACE}" != "cleanup" ] ; then
      new_labs="lxplus-scripts ${lxplus_type}-scripts"
    else
      new_labs="${lxplus_type} ${HOST_CMS_ARCH}-lxplus ${HOST_CMS_ARCH}-${lxplus_type} ${HOST_ARCH}"
    fi
    java ${JENKINS_CLI_OPTS} groovy $SCRIPT_DIR/set-slave-labels.groovy "${JENKINS_SLAVE_NAME}" "${new_labs} $(echo $TARGET | sed 's|.*@||')"
    ;;
  * )
    DOCKER_V=$(ssh -n $SSH_OPTS $TARGET docker --version 2>/dev/null || true)
    DOCKER=""
    if [ "${DOCKER_V}" != "" ] ; then
      if [ $(ssh -n $SSH_OPTS $TARGET id | grep '[0-9]*(docker)' | wc -l) -gt 0 ] ; then DOCKER="docker" ; fi
    fi
    new_labs="auto-label ${DOCKER} ${HOST_ARCH} ${HOST_CMS_ARCH}"
    case ${SLAVE_TYPE} in
      cmsbuild*|vocms*|cmsdev11 ) new_labs="${new_labs} cloud cmsbuild release-build";;
      cmsdev*   ) new_labs="${new_labs} cloud cmsdev";;
    esac
    for p in $(echo ${HOST_CMS_ARCH} | tr '_' ' ') ; do
      new_labs="${new_labs} ${p}"
    done
    java ${JENKINS_CLI_OPTS} groovy ${SCRIPT_DIR}/set-slave-labels.groovy "${JENKINS_SLAVE_NAME}" "${new_labs}"
    #java ${JENKINS_CLI_OPTS} groovy ${SCRIPT_DIR}/add-cpu-labels.groovy "${JENKINS_SLAVE_NAME}" "${HOST_ARCH}" "${HOST_CMS_ARCH}" "${DOCKER}"
    ;;
esac
if ! ssh -n $SSH_OPTS $TARGET test -f '~/.jenkins-slave-setup' ; then
  java ${JENKINS_CLI_OPTS} build 'jenkins-test-slave' -p SLAVE_CONNECTION=${TARGET} -p RSYNC_SLAVE_HOME=true -s || true
fi
ssh $SSH_OPTS $TARGET java -jar $WORKSPACE/slave.jar -jar-cache $WORKSPACE/tmp
