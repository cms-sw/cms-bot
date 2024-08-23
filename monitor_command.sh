#!/bin/bash

function monitor(){
  echo "=========== $1 ==============="
  date
  uptime
  free -g
  ps -u $(whoami) -o pid,start_time,pcpu,rss,size,vsize,cmd --forest
}

log="monitor_command_exit_code.txt"
("$@" || echo $? > ${log}) &
[ "${MONITOR_COMMAND_LOG}" = "" ] && MONITOR_COMMAND_LOG="monitor_command.log"
rm -f ${MONITOR_COMMAND_LOG} 
touch  ${MONITOR_COMMAND_LOG}
LOG_CHECK=$(date +%s)
monitor start >> ${MONITOR_COMMAND_LOG} 2>&1
while [ $(jobs -r -p | wc -l) -gt 0 ] ; do
  sleep 1
  CTIME=$(date +%s)
  let LOG_GAP=${CTIME}-${LOG_CHECK}
  if [ $LOG_GAP -lt 300 ] ; then continue ; fi
  LOG_CHECK=${CTIME}
  monitor >> ${MONITOR_COMMAND_LOG} 2>&1
done
wait
monitor end >> ${MONITOR_COMMAND_LOG} 2>&1
exit_code=0
[ -e ${log} ] && exit_code=$(cat ${log})
rm -f ${log}
cat ${MONITOR_COMMAND_LOG}
exit $exit_code
