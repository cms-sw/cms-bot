#!/bin/bash -e
env
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
JENKINS_SLAVE_JAR_MD5=$(md5sum ${WORKSPACE}/slave.jar | sed 's| .*||')
$WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}"
SLAVE_LABELS=$($WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}" | grep '^DATA_SLAVE_LABELS=' | sed 's|^DATA_SLAVE_LABELS=|condor |')
if [ $(nproc) -lt 8 ] ; then
  SLAVE_LABELS="${SLAVE_LABELS} scripts" 
fi
if [ "X${EXTRA_LABELS}" != "X" ] ; then SLAVE_LABELS="${SLAVE_LABELS} ${EXTRA_LABELS}" ;fi
if [ $(echo ${SLAVE_LABELS} | tr ' ' '\n' | grep '^cpu-xlarge$' | wc -l) -gt 0 ] ; then
  SLAVE_LABELS="${SLAVE_LABELS} cmsbuild"
fi

JENKINS_WEBHOOK="${JENKINS_WEBHOOK-https://cmssdt.cern.ch/SDT/cgi-bin/condor_webhook}"
JOB_ID=$(grep '^ *ClusterId *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g').0
SCHEDD_NAME=$(grep '^ *GlobalJobId *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s|#.*||;s|"||g')
TOKEN="$(sha256sum ~/private/secrets/github_hook_secret | sed 's| .*||')"
SIGNATURE=$(echo -n "${JOB_ID}:${WORKSPACE} ${TOKEN}" | sha256sum | sed 's| .*||')
JENKINS_PAYLOAD='{"jenkins_url":"'${JENKINS_CALLBACK}'","signature":"'${SIGNATURE}'","work_dir":"'${WORKSPACE}'","schedd_name":"'${SCHEDD_NAME}'","condor_job_id":"'${JOB_ID}'","labels":"'${SLAVE_LABELS}'","status":"@STATE@"}'

CURL_OPTS='-s -k -f --retry 3 --retry-delay 5 --max-time 30 -X POST'
if [ ! -f ${LOCAL_DATA}/online ] ; then
  SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|online|')
  curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
  touch ${LOCAL_DATA}/online
else
  SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|reconfigure|')
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
DEBUG_JOB=0
FORCE_EXIT=false
CHK_GAP=2
JENKINS_JOB_STATE="${JENKINS_AUTO_DELETE}-false"
if [ -f ${LOCAL_DATA}/offline ] ; then FORCE_EXIT=true ; fi
if [ "${JENKINS_DEBUG}" != "true" ] ; then set +x ; fi
CHECK_RUN=false
while true ; do
  sleep $CHK_GAP
  JENKINS_PROCESS=$(pgrep 'java' -a  | egrep "^[0-9]+\s+java\s+[-]jar\s+${WORKSPACE}/slave.jar\s+" | wc -l)
  if [ "${JENKINS_AUTO_DELETE}" != "true" ] ; then
    if [ ${JENKINS_PROCESS} -gt 0 ] ; then
      if $CHECK_RUN ; then
        echo "[$(date)] Stopping node check job" >> node-check.status
        touch ${WORKSPACE}/.auto-load
        wait
        CHECK_RUN=false
        echo "[$(date)] Stopped node check job" >> node-check.status
      fi
    elif ! $CHECK_RUN ; then
      CHECK_RUN=true
      echo "[$(date)] Starting node check job" >> node-check.status
      $WORKSPACE/cache/cms-bot/condor/tests/node-check.sh 2>&1 > node-check.log &
    fi
  fi
  if [ -f ${WORKSPACE}/.shut-down ] ; then sleep 60; break; fi
  CTIME=$(date +%s)
  if [ "${JENKINS_DEBUG}" = "true" ] ; then
    let DEBUG_JOB_GAP=$CTIME-${DEBUG_JOB}
    if [ $DEBUG_JOB_GAP -gt 300 ] ; then
      DEBUG_JOB=$CTIME
      if [ -e "/afs/cern.ch/user/c/cmsbuild/debug-grid-node.sh" ] ; then
        sh -ex /afs/cern.ch/user/c/cmsbuild/debug-grid-node.sh || true
      fi
    fi
  fi
  if [ ${JENKINS_PROCESS} -gt 0 ] ; then
    JENKINS_JOB_STATE="${JENKINS_AUTO_DELETE}-true"
    echo "Jenkins Slave has been conencted: $(date)"
  elif [ "${JENKINS_JOB_STATE}" = "true-true" ] ; then
    echo "Jenkins Slave has been disconencted: $(date)"
    break
  fi
  ls -drt ${_CONDOR_SCRATCH_DIR}/.condor_ssh_to_job_* 2>/dev/null | head -n -1 | xargs --no-run-if-empty rm -rf || true
  if [ $CTIME -gt ${FORCE_EXIT_AT} ] ; then
    break
  elif [ $CTIME -gt ${OFFLINE_NOTICE_TIME} -a "$FORCE_EXIT" = "false" ] ; then
    echo "Sending going to Offline notification"
    FORCE_EXIT=true
    SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|offline|')
    curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
    touch ${LOCAL_DATA}/offline
  fi
  let KERBEROS_REFRESH_GAP=$CTIME-$KERBEROS_REFRESH
  if [ $KERBEROS_REFRESH_GAP -gt 21600 ] ; then
    echo "Refreshing kerberose token"
    kinit -R || true
    KERBEROS_REFRESH=$CTIME
  fi
done
if $CHECK_RUN ; then touch ${WORKSPACE}/.auto-load ; wait ; fi
echo "Going to shutdown."
if [ "${JENKINS_DEBUG}" != "true" ] ; then set -x ; fi
rm -rf ${WORKSPACE}
if [ ! -f ${WORKSPACE}/.shut-down ] ; then
  SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|shutdown|')
  curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
fi
rm -rf ${WORKSPACE}
