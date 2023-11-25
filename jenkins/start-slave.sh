#!/bin/sh -ex
function get_data ()
{
  echo "$SYSTEM_DATA" | tr ';' '\n' | grep "^DATA_$1=" | sed 's|.*=||'
}

function get_env ()
{
  grep ">$1<" -A1 ${HOME}/nodes/${NODE_NAME}/config.xml | tail -1 | sed 's|[^>]*>||;s|<.*||'
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
DOCKER_IMG_HOST=$(get_env DOCKER_IMG_HOST)
MULTI_MASTER_SLAVE=$(get_env MULTI_MASTER_SLAVE)
EX_LABELS=$(get_env FORCE_LABELS)
JAVA_CMD=$(get_env JAVA_CMD)

JENKINS_SLAVE_JAR_MD5=$(md5sum ${HOME}/slave.jar | sed 's| .*||')
USER_HOME_MD5=""
if [ "${REMOTE_USER}" = "cmsbld" ] ; then
  USER_HOME_MD5=$(tar c ${HOME}/slave_setup/cmsbot 2>&1 | md5sum  | tail -1 | sed 's| .*||')
fi
#ssh -n $SSH_OPTS $TARGET aklog || true
SYS_SCRIPT="system-${REMOTE_USER}-$(hostname -s).sh"
scp -p $SSH_OPTS ${SCRIPT_DIR}/system-info.sh "$TARGET:/tmp/${SYS_SCRIPT}"
SYSTEM_DATA=$((ssh -n $SSH_OPTS $TARGET "/tmp/${SYS_SCRIPT} '${JENKINS_SLAVE_JAR_MD5}' '${WORKSPACE}' '${DOCKER_IMG_HOST}' '${CLEANUP_WORKSPACE}' '${USER_HOME_MD5}' '${JAVA_CMD}'" || echo "DATA_ERROR=Fail to run system-info.sh") | grep '^DATA_' | tr '\n' ';')

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
JENKINS_CLI_CMD="ssh -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ${HOME}/.ssh/id_rsa-openstack -l localcli -p ${SSHD_PORT} localhost"
JENKINS_API_URL=$(echo ${JENKINS_URL} | sed "s|^https://[^/]*/|http://localhost:${JENKINS_PORT}/|")
SET_KRB5CCNAME=true
CUR_LABS=$(grep '<label>' ${HOME}/nodes/${NODE_NAME}/config.xml |  sed 's|.*<label>||;s|</label>||')
if [ $(echo "${CUR_LABS}" | tr ' ' '\n' | grep '^no_label$' | wc -l) -eq 0 ] ; then
  slave_labels=""
  case ${SLAVE_TYPE} in
  *dmwm* ) slave_labels="cms-dmwm-cc7 no_label" ;;
  aiadm* ) echo "Skipping auto labels" ;;
  lxplus* )
    slave_labels=$(get_data SLAVE_LABELS)
    ;;
  * )
    slave_labels="auto-label $(get_data SLAVE_LABELS)"
    case ${SLAVE_TYPE} in
      cmsbuild*|vocms* ) slave_labels="${slave_labels} cloud cmsbuild release-build";;
      cmsdev*   )        slave_labels="${slave_labels} cloud cmsdev profiling";;
      * ) if [ $(echo "${CUR_LABS}" | tr ' ' '\n' | grep '^release-build$' | wc -l) -gt 0 ] ; then slave_labels="${slave_labels} release-build"; fi ;;
    esac
    case $(get_data HOST_CMS_ARCH) in
      *_aarch64|*_ppc64le ) slave_labels="${slave_labels} cmsbuild";;
    esac
    ;;
  esac
  if [ "${slave_labels}" != "" ] ; then
    slave_labels=$(echo ${slave_labels} ${EX_LABELS} | tr ' ' '\n' | sort | uniq | tr '\n' ' ' | sed 's|^ *||;s| *$||')
    if [ "${slave_labels}" != "${CUR_LABS}" ] ; then cat ${SCRIPT_DIR}/set-slave-labels.groovy | ${JENKINS_CLI_CMD} groovy = ${NODE_NAME} ${slave_labels} ; fi
  fi
fi
case ${SLAVE_TYPE} in
  lxplus* ) SET_KRB5CCNAME=false ;;
esac
if [ $(get_data JENKINS_SLAVE_SETUP) = "false" ] ; then
  case ${REMOTE_USER} in
    cmsbot|cmsbld)
      ${JENKINS_CLI_CMD} build 'jenkins-test-slave' -p SLAVE_CONNECTION=${TARGET} -p RSYNC_SLAVE_HOME=true -s || true
      ;;
     *) ;;
   esac
fi
if [ $(get_data SLAVE_JAR) = "false" ] ; then scp -p $SSH_OPTS ${HOME}/slave.jar $TARGET:$WORKSPACE/slave.jar ; fi
if $SET_KRB5CCNAME ; then
  KRB5_FILENAME=$(echo $KRB5CCNAME | sed 's|^FILE:||')
  scp -p $SSH_OPTS ${KRB5_FILENAME} $TARGET:/tmp/krb5cc_${REMOTE_USER_ID}
fi

pre_cmd=""
case $(get_data SHELL) in
  */tcsh|*/csh)
    pre_cmd="unlimit; limit"
    if $SET_KRB5CCNAME ; then pre_cmd="${pre_cmd}; setenv KRB5CCNAME FILE:/tmp/krb5cc_${REMOTE_USER_ID}" ; fi
    ;;
  *)
    pre_cmd="ulimit $(get_data LIMITS) >/dev/null 2>&1; ulimit -a"
    if $SET_KRB5CCNAME ; then pre_cmd="${pre_cmd} ; export KRB5CCNAME=FILE:/tmp/krb5cc_${REMOTE_USER_ID}" ; fi
    ;;
esac

pre_cmd="${pre_cmd} && (kinit -R || true) && (klist || true ) && "
EXTRA_JAVA_ARGS=""
if [ "${MULTI_MASTER_SLAVE}" = "true" ] ; then
  #set +x
  let MAX_WAIT_TIME=60*60*12
  WAIT_GAP=60
  SLAVE_CMD_REGEX="^java\s+-DMULTI_MASTER_SLAVE=true\s+.*\s+"
  START_ALL_SHARED=true
  while true ; do
    if [ $(grep '</temporaryOfflineCause>' ${HOME}/nodes/${NODE_NAME}/config.xml | wc -l) -eq 0 ] ; then
      if [ $(ssh -n $SSH_OPTS $TARGET "pgrep -f '${SLAVE_CMD_REGEX}' | wc -l") -eq 0 ] ; then break ; fi
    fi
    if $START_ALL_SHARED ; then
      START_ALL_SHARED=false
      shared_labels=$(curl -s ${JENKINS_API_URL}/computer/${NODE_NAME}/api/xml  | sed 's|<assignedLabel>|\n|g' | sed 's|</name>.*||;s|<name>||' | grep '^shared-')
      for s in ${shared_labels} ; do
        for node in $(curl -s ${JENKINS_API_URL}/label/$s/api/xml | sed 's|<nodeName>|\n|g' | grep '</nodeName>' | sed 's|</nodeName>.*||') ; do
          [ "${node}" = "${NODE_NAME}" ] && continue
          [ $(grep '</temporaryOfflineCause>' ${HOME}/nodes/${node}/config.xml | wc -l) -gt 0 ] && continue
          pgrep -f " +${node}\s*\$" || true
          if [ $(pgrep -f " +${node}\s*\$" | wc -l) -eq 0 ] ; then
            (nohup ${JENKINS_CLI_CMD} connect-node $node >/dev/null 2>&1  &) || true
            break
          fi
        done
      done
    fi
    echo "$(date): Waiting $MAX_WAIT_TIME ..."
    if [ $MAX_WAIT_TIME -gt 0 ] ; then
      let MAX_WAIT_TIME=$MAX_WAIT_TIME-$WAIT_GAP
      sleep $WAIT_GAP
      if [ $(grep '</temporaryOfflineCause>' ${HOME}/nodes/${NODE_NAME}/config.xml | wc -l) -gt 0 ] ; then
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
JAVA=${JAVA_CMD}
if [ "${JAVA}" = "" ] ; then
  JAVA=$(get_data JAVA)
  if [ "${JAVA}" = "" ] ; then JAVA="java"; fi
fi
ssh $SSH_OPTS $TARGET "${pre_cmd} ${JAVA} ${EXTRA_JAVA_ARGS} \
  --add-opens java.base/java.lang=ALL-UNNAMED \
  --add-opens java.base/java.lang.reflect=ALL-UNNAMED \
  -jar $WORKSPACE/slave.jar -jar-cache $WORKSPACE/tmp"
