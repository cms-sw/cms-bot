#!/bin/bash -e
#########################################
JOBS_STATUS_0='Unexpanded'
JOBS_STATUS_1='Idle'
JOBS_STATUS_2='Running'
JOBS_STATUS_3='Removed'
JOBS_STATUS_4='Completed'
JOBS_STATUS_5='Held'
JOBS_STATUS_6='Submission_Error'
JOBS_STATUS_='Unknown'

WAIT_GAP=60
ERROR_COUNT=0
MAX_ERROR_COUNT=5
WORKSPACE="${WORKSPACE-$PWD}"
JOB_NAME="${JOB_NAME-job}"
BUILD_NUMBER="${BUILD_NUMBER-0}"
REQUEST_CPUS="${REQUEST_CPUS-1}"
REQUEST_UNIVERSE="${REQUEST_UNIVERSE-vanilla}"
REQUEST_MAXRUNTIME="${REQUEST_MAXRUNTIME-432000}"
JENKINS_DEBUG="${DEBUG-false}"

if [ $REQUEST_CPUS -lt 1 ] ; then REQUEST_CPUS=1 ; fi
if [ "${REQUEST_MEMORY}" == "" ] ; then let REQUEST_MEMORY=${REQUEST_CPUS}*2500 ; fi
if [ $REQUEST_MAXRUNTIME -lt 3600 ] ; then REQUEST_MAXRUNTIME=3600 ; fi
##########################################
here=$(dirname $0)
cd $WORKSPACE
mkdir -p logs

script_name=${JOB_NAME}-${NODE_ARCH}-${BUILD_NUMBER}.$(date +%Y%m%d)
SLAVE_JAR_DIR="${WORKSPACE}"
while [ ! -e ${SLAVE_JAR_DIR}/slave.jar ] ; do
  SLAVE_JAR_DIR=$(dirname $SLAVE_JAR_DIR)
  if [ "${SLAVE_JAR_DIR}" = "/" ] ; then
    echo "ERROR: Unable to find slave.jar under ${WORKSPACE}"
    exit 1
  fi
done
INPUT_FILES=""
for xfile in ${SLAVE_JAR_DIR}/slave.jar ; do
  if [ -e $xfile ] ; then
    xname=$(basename $xfile)
    cp $xfile ./${xname}
    chmod 0600 ./${xname}
    INPUT_FILES="${xname},${INPUT_FILES}"
  fi
done
INPUT_FILES=$(echo ${INPUT_FILES} | sed 's|,$||')
cp ${here}/connect.sub job.sub
cp ${here}/connect-job.sh  ${script_name}.sh
chmod +x ${script_name}.sh

sed -i -e "s|@SCRIPT_NAME@|${script_name}|"             job.sub
sed -i -e "s|@REQUEST_CPUS@|$REQUEST_CPUS|"             job.sub
sed -i -e "s|@REQUEST_MEMORY@|$REQUEST_MEMORY|"         job.sub
sed -i -e "s|@REQUEST_UNIVERSE@|$REQUEST_UNIVERSE|"     job.sub
sed -i -e "s|@REQUEST_MAXRUNTIME@|$REQUEST_MAXRUNTIME|" job.sub
sed -i -e "s|@INPUT_FILES@|$INPUT_FILES|"               job.sub
echo "environment = \"JENKINS_DEBUG='${JENKINS_DEBUG}' JENKINS_AUTO_DELETE='${JENKINS_AUTO_DELETE}' EXTRA_LABELS='${EXTRA_LABELS}' JENKINS_PREFIX='${JENKINS_PREFIX}' REQUEST_MAXRUNTIME=${REQUEST_MAXRUNTIME}\"" >> job.sub

if [ "X${CONDOR_JOB_CONF}" != "X" ] ; then
  if [ -f  ${CONDOR_JOB_CONF} ] ; then
    cat ${CONDOR_JOB_CONF} >> job.sub
  else
    echo "ERROR: Missing condor job configuration file : ${CONDOR_JOB_CONF}"
    exit 1
  fi
fi
echo "queue 1" >> job.sub
echo "############# JOB Configuration file ###############"
cat job.sub
echo "####################################################"

JOBID=""
if [ "$USE_PENDING_REQUEST" = "true" ] ; then
  for x in $(condor_q `whoami` -global -format "%s:" JobStatus -format "%s:" ClusterId -format "%s:" GlobalJobId -format "%s\n" Cmd | grep ":${JOB_NAME}") ; do
    status=$(echo $x | cut -d: -f1)
    jid=$(echo $x | cut -d: -f2)
    schd=$(echo $x | cut -d: -f3 | cut -d# -f1)
    if [ $status -gt 2 -o $status -eq 0 ] ; then
      ${here}/shutdown.sh $jid || true
    elif [ $status -eq 1 ] ; then
      JOBID="${jid}.0"
      echo "Using existing job $JOBID (${schd})"
      export _CONDOR_SCHEDD_HOST="${schd}"
      export _CONDOR_CREDD_HOST="${schd}"
    else
      echo "Already running $jid"
      sleep 600
      exit 0
    fi
  done
fi
if [ "${JOBID}" = "" ] ; then
  condor_submit -spool ${CONDOR_SUBMIT_OPTIONS} job.sub > submit.log 2>&1 || true
  cat submit.log
  JOBID=$(grep ' submitted to cluster ' submit.log | sed 's|.* ||;s| ||g;s|\.$||')
fi
if [ "$JOBID" = "" ] ; then exit 1 ; fi
sleep $WAIT_GAP
echo "$JOBID" > job.id

EXIT_CODE=1
PREV_JOB_STATUS=""
KINIT_COUNT=0
kinit -R
RUN_CHECK=false
while true ; do
  JOB_STATUS=$(condor_q -json -attributes JobStatus $JOBID | grep 'JobStatus' | sed 's|.*: *||;s| ||g')
  eval JOB_STATUS_MSG=$(echo \$$(echo JOBS_STATUS_${JOB_STATUS}))
  if [ "${PREV_JOB_STATUS}" != "${JOB_STATUS}${ERROR_COUNT}" ] ; then
    echo "Job Status(${ERROR_COUNT}): $JOB_STATUS: ${JOB_STATUS_MSG}"
    PREV_JOB_STATUS="${JOB_STATUS}${ERROR_COUNT}"
  fi
  if [ "$JOB_STATUS" = "1" -o "$JOB_STATUS" = "2" ] ;  then
    ERROR_COUNT=0
    if [ "$JOB_STATUS" = "2" ] ;  then
      if $RUN_CHECK ; then
        exit 0
      else
        RUN_CHECK=true
      fi
    fi
  elif [ "$JOB_STATUS" = "4" ] ; then
    EXIT_CODE=$(condor_q -json -attributes ExitCode $JOBID | grep 'ExitCode' | sed 's|.*: *||;s| ||g')
    break
  elif [ "$JOB_STATUS" = "3" -o "$JOB_STATUS" = "6" -o "$JOB_STATUS" = "0" ] ;  then
    ERROR_COUNT=$MAX_ERROR_COUNT
  else
    if [ "$JOB_STATUS" = "5" ] ; then condor_q -json -attributes HoldReason $JOBID | grep 'HoldReason' | sed 's|"||g;s|^ *HoldReason: *||' || true ; fi
    let ERROR_COUNT=$ERROR_COUNT+1
  fi
  if [ $ERROR_COUNT -ge $MAX_ERROR_COUNT ] ; then
    condor_q -json -attributes $JOBID || true
    break
  fi
  sleep $WAIT_GAP
  let KINIT_COUNT=KINIT_COUNT+1
  if [ $KINIT_COUNT -ge 120 ] ; then
    KINIT_COUNT=0
    kinit -R
    klist
  fi
done
echo EXIT_CODE $EXIT_CODE
condor_transfer_data $JOBID || true
ls -l
cat logs/log.* || true
cat log.job || true
condor_rm $JOBID || true
condor_q
exit $EXIT_CODE

