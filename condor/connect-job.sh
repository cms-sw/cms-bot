#!/bin/bash -ex

function set_jenkins_callback()
{
  pushd $WORKSPACE/cache/cms-bot
    git pull --rebase || git pull --rebase
    export JENKINS_CALLBACK=$(python3 -c "import cms_static;print(cms_static.get_jenkins('${JENKINS_PREFIX}'))")
  popd
}

function jenkins_data()
{
  echo "${JENKINS_PAYLOAD}" | sed "s|@STATE@|$1|;s|@JENKINS_CALLBACK@|${JENKINS_CALLBACK}|"
}

env
ls -la
if [ "${_CONDOR_JOB_AD}" != "" ] ; then
  [ -e ${_CONDOR_JOB_AD} ] && cat ${_CONDOR_JOB_AD}
fi
if [ "${_CONDOR_MACHINE_AD}" != "" ] ; then
  if [ -e ${_CONDOR_MACHINE_AD} ] ; then
    cat ${_CONDOR_MACHINE_AD}
    xnum=$(grep -i '^cpus *= *' ${_CONDOR_MACHINE_AD} | sed 's|.*=||;s| ||g')
    if [ "${xnum}" != "" ] ; then export JENKINS_AGENT_CORES=${xnum} ; fi
    #xnum=$(grep -i '^memory *= *' ${_CONDOR_MACHINE_AD} | sed 's|.*=||;s| ||g')
    #if [ "${xnum}" != "" ] ; then export JENKINS_AGENT_MEMORY=${xnum} ; fi
  fi
fi
if [ "${USER}" = "" ] ; then export USER=$(whoami); fi
LOCAL_DATA=${_CONDOR_SCRATCH_DIR}/cmsconnect
mkdir -p ${LOCAL_DATA}
if [ -f ${LOCAL_DATA}/start_time ] ; then
  START_TIME=$(cat ${LOCAL_DATA}/start_time | head -1)
else
  START_TIME=$(date +%s)
  echo "$START_TIME" > ${LOCAL_DATA}/start_time
fi
export WORKSPACE=${_CONDOR_SCRATCH_DIR}/jenkins
rm -rf ${WORKSPACE}
mkdir -p $WORKSPACE/cache $WORKSPACE/workspace ${WORKSPACE}/tmp
git clone --depth 1 https://github.com/cms-sw/cms-bot $WORKSPACE/cache/cms-bot
mv slave.jar ${WORKSPACE}/
AFS_HOME=/afs/cern.ch/user/${USER::1}/${USER}
for x in .netrc tnsnames.ora .cms_cond/db.key ; do
  [ ! -e $x ] || continue
  [ -e ${AFS_HOME}/$x ] || continue
  [ $(dirname $x) = "." ] || mkdir -p $(dirname $x)
  cp -p ${AFS_HOME}/$x $x || true
done
JENKINS_SLAVE_JAR_MD5=$(md5sum ${WORKSPACE}/slave.jar | sed 's| .*||')
$WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}"

SLAVE_LABELS=$($WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}" | grep '^DATA_SLAVE_LABELS=' | sed 's|^DATA_SLAVE_LABELS=|condor |')
xcore=${JENKINS_AGENT_CORES}
[ "${xcore}" = "" ] && xcore=$(nproc)
if [ ${xcore} -lt 8 ] ; then
  SLAVE_LABELS="${SLAVE_LABELS} scripts" 
elif [ ${xcore} -gt 8 ] ; then
  SLAVE_LABELS="${SLAVE_LABELS} cmsbuild"
fi
if [ "X${EXTRA_LABELS}" != "X" ] ; then SLAVE_LABELS="${SLAVE_LABELS} ${EXTRA_LABELS}" ;fi
set_jenkins_callback

JENKINS_WEBHOOK="${JENKINS_WEBHOOK-https://cmssdt.cern.ch/SDT/cgi-bin/condor_webhook}"
JOB_ID=$(grep '^ *ClusterId *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g').0
SCHEDD_NAME=$(grep '^ *GlobalJobId *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s|#.*||;s|"||g')
TOKEN="$(sha256sum ${AFS_HOME}/private/secrets/github_hook_secret | sed 's| .*||')"
SIGNATURE=$(echo -n "${JOB_ID}:${WORKSPACE} ${TOKEN}" | sha256sum | sed 's| .*||')
JENKINS_PAYLOAD='{"jenkins_url":"@JENKINS_CALLBACK@","signature":"'${SIGNATURE}'","work_dir":"'${WORKSPACE}'","schedd_name":"'${SCHEDD_NAME}'","condor_job_id":"'${JOB_ID}'","labels":"'${SLAVE_LABELS}'","status":"@STATE@"}'

CURL_OPTS='-s -k -f --retry 3 --retry-delay 5 --max-time 30 -X POST'
if [ ! -f ${LOCAL_DATA}/online ] ; then
  SEND_DATA=$(jenkins_data online)
  curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
  touch ${LOCAL_DATA}/online
else
  SEND_DATA=$(jenkins_data reconfigure)
  curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
fi

REQUEST_MAXRUNTIME=$(grep '^ *MaxRuntime *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
let OFFLINE_NOTICE_SEC="${REQUEST_MAXRUNTIME}/10"
if [ ${OFFLINE_NOTICE_SEC} -gt 43200 ] ; then OFFLINE_NOTICE_SEC=43200; fi
let FORCE_EXIT_SEC="${OFFLINE_NOTICE_SEC}/10"
if [ $FORCE_EXIT_SEC -gt 300 ] ; then FORCE_EXIT_SEC=300; fi
if [ $FORCE_EXIT_SEC -lt 60 ] ; then FORCE_EXIT_SEC=60; fi
let OFFLINE_NOTICE_TIME=${START_TIME}+${REQUEST_MAXRUNTIME}-${OFFLINE_NOTICE_SEC}
let FORCE_EXIT_AT=${START_TIME}+${REQUEST_MAXRUNTIME}-${FORCE_EXIT_SEC}

KERBEROS_REFRESH=0
CHECK_JOB=0
FORCE_EXIT=false
CHK_GAP=2
JENKINS_JOB_STATE="${JENKINS_AUTO_DELETE}-false"
if [ -f ${LOCAL_DATA}/offline ] ; then FORCE_EXIT=true ; fi
if [ "${JENKINS_DEBUG}" != "true" ] ; then set +x ; fi
CHECK_RUN=false
touch node-check.status
while true ; do
  sleep $CHK_GAP
  SSH_JOBS=0
  if [ "${JENKINS_AUTO_DELETE}" != "true" ] ; then
    source $WORKSPACE/cache/cms-bot/condor/autoload.sh || true
  else
    SSH_JOBS=$(ls -d ${_CONDOR_SCRATCH_DIR}/.condor_ssh_to_job_* 2>/dev/null | wc -l)
  fi
  if [ -f ${WORKSPACE}/.shut-down ] ; then sleep 60; break; fi
  CTIME=$(date +%s)
  let JOB_GAP=${CTIME}-${CHECK_JOB}
  if [ $JOB_GAP -lt 60 ] ; then continue ; fi
  CHECK_JOB=$CTIME
  if [ ${SSH_JOBS} -gt 0 ] ; then
    JENKINS_JOB_STATE="${JENKINS_AUTO_DELETE}-true"
    echo "Jenkins Slave has been conencted: $(date)"
  elif [ "${JENKINS_JOB_STATE}" = "true-true" ] ; then
    echo "Jenkins Slave has been disconencted: $(date)"
    break
  fi
  if [ "${JENKINS_DEBUG}" = "true" ] ; then
    if [ -e "/afs/cern.ch/user/c/cmsbuild/debug-grid-node.sh" ] ; then
      sh -ex /afs/cern.ch/user/c/cmsbuild/debug-grid-node.sh || true
    fi
  fi
  if [ $CTIME -gt ${FORCE_EXIT_AT} ] ; then
    break
  elif [ $CTIME -gt ${OFFLINE_NOTICE_TIME} -a "$FORCE_EXIT" = "false" ] ; then
    echo "Sending going to Offline notification"
    FORCE_EXIT=true
    set_jenkins_callback
    SEND_DATA=$(jenkins_data offline)
    curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
    touch ${LOCAL_DATA}/offline
  fi
  let JOB_GAP=$CTIME-$KERBEROS_REFRESH
  if [ $JOB_GAP -gt 21600 ] ; then
    echo "Refreshing kerberose token"
    kinit -R || true
    KERBEROS_REFRESH=$CTIME
  fi
done
if $CHECK_RUN ; then touch ${WORKSPACE}/.auto-stop ; wait ; fi
echo "Going to shutdown."
if [ "${JENKINS_DEBUG}" != "true" ] ; then set -x ; fi
rm -rf ${WORKSPACE}
if [ ! -f ${WORKSPACE}/.shut-down ] ; then
  set_jenkins_callback
  SEND_DATA=$(jenkins_data shutdown)
  curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
fi
rm -rf ${WORKSPACE}
