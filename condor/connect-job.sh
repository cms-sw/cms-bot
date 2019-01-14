#!/bin/bash -ex
START_TIME=$(date +%s)
export WORKSPACE=${_CONDOR_SCRATCH_DIR}/jenkins
rm -rf ${WORKSPACE}
mkdir -p $WORKSPACE/cache $WORKSPACE/workspace ${WORKSPACE}/tmp
git clone --depth 1 git@github.com:cms-sw/cms-bot $WORKSPACE/cache/cms-bot
mv slave.jar ${WORKSPACE}/
JENKINS_SLAVE_JAR_MD5=$(md5sum ${WORKSPACE}/slave.jar | sed 's| .*||')
$WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}"
SLAVE_LABELS=$($WORKSPACE/cache/cms-bot/jenkins/system-info.sh "${JENKINS_SLAVE_JAR_MD5}" "${WORKSPACE}" | grep '^DATA_SLAVE_LABELS=' | sed 's|^DATA_SLAVE_LABELS=|condor |')
if [ $(nproc) -lt 8 ] ; then
  SLAVE_LABELS="${SLAVE_LABELS} scripts" 
fi

JENKINS_WEBHOOK="${JENKINS_WEBHOOK-https://cmssdt.cern.ch/SDT/cgi-bin/condor_webhook}"
JOB_ID=$(grep '^ *ClusterId *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g').0
TOKEN="$(sha256sum ~/private/secrets/github_hook_secret | sed 's| .*||')"
SIGNATURE=$(echo -n "${JOB_ID}:${WORKSPACE} ${TOKEN}" | sha256sum | sed 's| .*||')
JENKINS_PAYLOAD='{"jenkins_url":"@JENKINS_CALLBACK@","signature":"'${SIGNATURE}'","work_dir":"'${WORKSPACE}'", "condor_job_id":"'${JOB_ID}'", "labels":"'${SLAVE_LABELS}'", "status":"@STATE@"}'

CURL_OPTS='-s -k -f --retry 3 --retry-delay 5 --max-time 30 -X POST'
SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|online|')
curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"

JENKINS_PAYLOAD='{"jenkins_url":"@JENKINS_CALLBACK@","signature":"'${SIGNATURE}'","work_dir":"", "condor_job_id":"'${JOB_ID}'", "labels":"", "status":"@STATE@"}'
REQUEST_MAXRUNTIME=$(grep '^ *MaxRuntime *=' ${_CONDOR_JOB_AD} | sed 's|.*= *||;s| ||g')
let OFFLINE_NOTICE_SEC="${REQUEST_MAXRUNTIME}/10"
let FORCE_EXIT_SEC="${OFFLINE_NOTICE_SEC}/10"
if [ $FORCE_EXIT_SEC -gt 300 ] ; then FORCE_EXIT_SEC=300; fi
if [ $FORCE_EXIT_SEC -lt 60 ] ; then FORCE_EXIT_SEC=60; fi
let OFFLINE_NOTICE_TIME=${START_TIME}+${REQUEST_MAXRUNTIME}-${OFFLINE_NOTICE_SEC}
let FORCE_EXIT_AT=${START_TIME}+${REQUEST_MAXRUNTIME}-${FORCE_EXIT_SEC}

KERBEROS_REFRESH=0
FORCE_EXIT=false
CHK_GAP=60
while true ; do
  sleep $CHK_GAP
  CTIME=$(date +%s)
  if $FORCE_EXIT ; then
    if [ -f ${WORKSPACE}/.shut-down ] ; then sleep 60; break; fi
    if [ $CTIME -gt ${FORCE_EXIT_AT} ]     ; then break ; fi
  elif [ $CTIME -gt ${OFFLINE_NOTICE_TIME} ] ; then
    echo exit > ${WORKSPACE}/.auto-load
    FORCE_EXIT=true
    SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|offline|')
    curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
  fi
  let KERBEROS_REFRESH_GAP=$CTIME-$KERBEROS_REFRESH
  if [ $KERBEROS_REFRESH_GAP -gt 21600 ] ; then
    kinit -R
    KERBEROS_REFRESH=$CTIME
  fi
done
rm -rf ${WORKSPACE}
SEND_DATA=$(echo "${JENKINS_PAYLOAD}" | sed 's|@STATE@|shutdown|')
curl ${CURL_OPTS} -d "${SEND_DATA}" --header 'Content-Type: application/json' "${JENKINS_WEBHOOK}"
