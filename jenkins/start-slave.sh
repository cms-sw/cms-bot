#!/bin/sh -ex
function get_data ()
{
  echo "$SYSTEM_DATA" | tr ';' '\n' | grep "^DATA_$1=" | sed 's|.*=||'
}

SCRIPT_DIR=$(cd $(dirname $0); /bin/pwd)
TARGET=$1
CLEANUP_WORKSPACE=$2
REMOTE_USER=$(echo $TARGET | sed 's|@.*||')
SSH_OPTS="-q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60"

#Check unique slave conenction
if [ "${SLAVE_UNIQUE_TARGET}" = "YES" ] ; then
  TARGET_HOST=$(echo $TARGET | sed 's|.*@||')
  if [ `pgrep -f "@${TARGET_HOST} " | grep -v "$$" | wc -l` -gt 1 ] ; then exit 99 ; fi
fi
DOCKER_IMG_HOST=$(grep '>DOCKER_IMG_HOST<' -A1 ${HOME}/nodes/${NODE_NAME}/config.xml | tail -1  | sed 's|[^>]*>||;s|<.*||')
MULTI_MASTER_SLAVE=$(grep '>MULTI_MASTER_SLAVE<' -A1 ${HOME}/nodes/${NODE_NAME}/config.xml | tail -1  | sed 's|[^>]*>||;s|<.*||')

JENKINS_SLAVE_JAR_MD5=$(md5sum ${HOME}/slave.jar | sed 's| .*||')
USER_HOME_MD5=""
if [ "${REMOTE_USER}" = "cmsbld" ] ; then
  USER_HOME_MD5=$(tar c ${HOME}/slave_setup/cmsbot 2>&1 | md5sum  | tail -1 | sed 's| .*||')
elif [ "${REMOTE_USER}" = "cmsbuild" ] ; then
  ssh -n $SSH_OPTS $TARGET aklog || true
fi
ssh -n $SSH_OPTS $TARGET aklog || true
scp -p $SSH_OPTS ${SCRIPT_DIR}/system-info.sh "$TARGET:~/system-info.sh"
SYSTEM_DATA=$((ssh -n $SSH_OPTS $TARGET "~/system-info.sh '${JENKINS_SLAVE_JAR_MD5}' '${WORKSPACE}' '${DOCKER_IMG_HOST}' '${CLEANUP_WORKSPACE}' '${USER_HOME_MD5}'" || echo "DATA_ERROR=Fail to run system-info.sh") | grep '^DATA_' | tr '\n' ';')

if [ $(get_data ERROR | wc -l) -gt 0 ] ; then
  echo $DATA | tr ';' '\n'
  exit 1
fi

#Check slave workspace size in GB
if [ "${SLAVE_MAX_WORKSPACE_SIZE}" != "" ] ; then
  if [ $(get_data WORKSPACE_SIZE) -lt $SLAVE_MAX_WORKSPACE_SIZE ] ; then exit 99 ; fi
fi

if [ $(get_data RSYNC_SLAVE) = "true" ] ; then
  rsync -e "ssh $SSH_OPTS" -av ${HOME}/slave_setup/cmsbot/ ${TARGET}:~/
  ssh -n $SSH_OPTS $TARGET "echo '${USER_HOME_MD5}' > ~/.jenkins_slave_md5"
fi
REMOTE_USER_ID=$(get_data REMOTE_USER_ID)
JENKINS_PORT=$(pgrep -x -a  -f ".*httpPort=.*" | tail -1 | tr ' ' '\n' | grep httpPort | sed 's|.*=||')
SSHD_PORT=$(grep '<port>' ${HOME}/org.jenkinsci.main.modules.sshd.SSHD.xml | sed 's|</.*||;s|.*>||')
JENKINS_CLI_CMD="ssh -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ${HOME}/.ssh/id_dsa -l localcli -p ${SSHD_PORT} localhost"
if [ $(cat ${HOME}/nodes/${NODE_NAME}/config.xml | grep '<label>' | grep 'no_label' | wc -l) -eq 0 ] ; then
  slave_labels=""
  case ${SLAVE_TYPE} in
  *dmwm* ) echo "Skipping auto labels" ;;
  aiadm* ) echo "Skipping auto labels" ;;
  lxplus* )
    slave_labels=$(get_data SLAVE_LABELS)
    ;;
  * )
    slave_labels="auto-label $(get_data SLAVE_LABELS)"
    case ${SLAVE_TYPE} in
      cmsbuild*|vocms* ) slave_labels="${slave_labels} cloud cmsbuild release-build";;
      cmsdev*   ) slave_labels="${slave_labels} cloud cmsdev";;
    esac
    case $(get_data HOST_CMS_ARCH) in
      *_aarch64|*_ppc64le ) slave_labels="${slave_labels} release-build cmsbuild";;
    esac
    ;;
  esac
  slave_labels=$(echo ${slave_labels} | sed 's|  *| |g;s|^ *||;s| *$||')
  if [ "X${slave_labels}" != "X" ] ; then cat ${SCRIPT_DIR}/set-slave-labels.groovy | ${JENKINS_CLI_CMD} groovy = ${NODE_NAME} ${slave_labels} ; fi
fi
if [ $(get_data JENKINS_SLAVE_SETUP) = "false" ] ; then
  case ${REMOTE_USER} in
    cmsbot|cmsbld)
      ${JENKINS_CLI_CMD} build 'jenkins-test-slave' -p SLAVE_CONNECTION=${TARGET} -p RSYNC_SLAVE_HOME=true -s || true
      ;;
     *) ;;
   esac
fi
KRB5_FILENAME=$(echo $KRB5CCNAME | sed 's|^FILE:||')
if [ $(get_data SLAVE_JAR) = "false" ] ; then scp -p $SSH_OPTS ${HOME}/slave.jar $TARGET:$WORKSPACE/slave.jar ; fi
scp -p $SSH_OPTS ${KRB5_FILENAME} $TARGET:/tmp/krb5cc_${REMOTE_USER_ID}

pre_cmd=""

case $TARGET in
  cmsdev*)
    limits="-a";;
  *)
    limits=$(get_data LIMITS);;

case $(get_data SHELL) in
  */tcsh|*/csh) pre_cmd="unlimit; limit; setenv KRB5CCNAME FILE:/tmp/krb5cc_${REMOTE_USER_ID}" ;;
  *) pre_cmd="ulimit $limits >/dev/null 2>&1; ulimit -a; export KRB5CCNAME=FILE:/tmp/krb5cc_${REMOTE_USER_ID}" ;;
esac

pre_cmd="${pre_cmd} && (kinit -R || true) && (klist || true ) && "
EXTRA_JAVA_ARGS=""
if [ "${MULTI_MASTER_SLAVE}" = "true" ] ; then
  set +x
  let MAX_WAIT_TIME=60*60*12
  WAIT_GAP=60
  SLAVE_CMD_REGEX="^java\s+-DMULTI_MASTER_SLAVE=true\s+-jar\s+.*/slave.*\s+"
  while true ; do
    if [ $(ssh -n $SSH_OPTS $TARGET "pgrep -f '${SLAVE_CMD_REGEX}' | wc -l") -eq 0 ] ; then break ; fi
    echo "$(date): Waiting $MAX_WAIT_TIME ..."
    if [ $MAX_WAIT_TIME -gt 0 ] ; then
      let MAX_WAIT_TIME=$MAX_WAIT_TIME-$WAIT_GAP
      sleep $WAIT_GAP
      if [ $(grep '</temporaryOfflineCause>' ${HOME}/nodes/$i{NODE_NAME}/config.xml | wc -l) -gt 0 ] ; then
        echo "ERROR: Node is marked temporary Offline, so exiting without connecting."
        exit 0
      fi
    else
      exit 1
    fi
  done
  set -x
  pre_cmd="${pre_cmd} pgrep -f  '${SLAVE_CMD_REGEX}' && exit 1 || "
  EXTRA_JAVA_ARGS="-DMULTI_MASTER_SLAVE=true"
fi
if [ $(grep '</temporaryOfflineCause>' ${HOME}/nodes/${NODE_NAME}/config.xml | wc -l) -gt 0 ] ; then
  echo "ERROR: Node is marked temporary Offline, so exiting without connecting."
  exit 0
fi
ssh $SSH_OPTS $TARGET "${pre_cmd} java ${EXTRA_JAVA_ARGS} -jar $WORKSPACE/slave.jar -jar-cache $WORKSPACE/tmp"
