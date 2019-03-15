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
REQUEST_MAXRUNTIME="${REQUEST_MAXRUNTIME-7200}"
##########################################
cd $WORKSPACE

here=$(dirname $0)
script_name=${JOB_NAME}-${BUILD_NUMBER}.$(date +%Y%m%d%H%M%S)

X509_PROXY_FILE="x509up_u$(id -u)"
voms-proxy-init --voms cms --out $X509_PROXY_FILE
chmod 0600 $X509_PROXY_FILE

echo '#!/bin/bash -ex' > ${script_name}.sh
echo 'export WORKSPACE=${_CONDOR_SCRATCH_DIR}' >> ${script_name}.sh
echo "export X509_USER_PROXY=\${WORKSPACE}/$X509_PROXY_FILE" >> ${script_name}.sh
echo "#### User Script #### " >> ${script_name}.sh
cat $1 | grep -v "/condor/submit.sh  *" >> ${script_name}.sh
chmod +x ${script_name}.sh
cp ${here}/submit.sub job.sub
sed -i -e "s|@SCRIPT_NAME@|${script_name}|"             job.sub
sed -i -e "s|@REQUEST_CPUS@|$REQUEST_CPUS|"             job.sub
sed -i -e "s|@REQUEST_UNIVERSE@|$REQUEST_UNIVERSE|"     job.sub
sed -i -e "s|@REQUEST_MAXRUNTIME@|$REQUEST_MAXRUNTIME|" job.sub
sed -i -e "s|@X509_PROXY_FILE@|$X509_PROXY_FILE|"       job.sub
if [ "$DEBUG" = "true" ] ; then
  echo "############# JOB Configuration file ###############"
  cat job.sub
  echo "####################################################"
  cat ${script_name}.sh
  echo "####################################################"
fi
unset REQUEST_MAXRUNTIME REQUEST_UNIVERSE REQUEST_CPUS DEBUG X509_PROXY_FILE
condor_submit -spool ${CONDOR_SUBMIT_OPTIONS} job.sub > submit.log 2>&1
cat submit.log
rm -f $X509_PROXY_FILE
JOBID=$(grep ' submitted to cluster ' submit.log | sed 's|.* ||;s| ||g;s|\.$||')
if [ "$JOBID" = "" ] ; then exit 1 ; fi
sleep $WAIT_GAP
echo "$JOBID" > job.id

EXIT_CODE=1
PREV_JOB_STATUS=""
while true ; do
  JOB_STATUS=$(condor_q -json -attributes JobStatus $JOBID | grep 'JobStatus' | sed 's|.*: *||;s| ||g')
  eval JOB_STATUS_MSG=$(echo \$$(echo JOBS_STATUS_${JOB_STATUS}))
  if [ "${PREV_JOB_STATUS}" != "${JOB_STATUS}${ERROR_COUNT}" ] ; then
    echo "Job Status(${ERROR_COUNT}): $JOB_STATUS: ${JOB_STATUS_MSG}"
    PREV_JOB_STATUS="${JOB_STATUS}${ERROR_COUNT}"
  fi
  if [ "$JOB_STATUS" = "1" -o "$JOB_STATUS" = "2" ] ;  then
    ERROR_COUNT=0
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
done
echo EXIT_CODE $EXIT_CODE
condor_transfer_data $JOBID || condor_transfer_data $JOBID || condor_transfer_data $JOBID || condor_transfer_data $JOBID true
ls -l
if [ -f ${script_name}.stdout ] ; then cat ${script_name}.stdout ; fi
condor_rm $JOBID || condor_rm $JOBID || condor_rm $JOBID || condor_rm $JOBID || true
exit $EXIT_CODE
