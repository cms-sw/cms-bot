#!/bin/bash -ex

IB_WEEK_DIR="/cvmfs/cms-ib.cern.ch/week0 /cvmfs/cms-ib.cern.ch/week1 /cvmfs/cms.cern.ch"
RELEASE=$1
ARCH=$2
WAIT_STEP=$3
MAX_WAIT=$4
if [ "X$RELEASE" = "X" ] ; then echo "Error: Missing release name"     ; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi
if [ "X$ARCH" = "X" ]    ; then echo "Error: Missing architecture name"; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi

if [ "X$WAIT_STEP" = "X" ] ; then WAIT_STEP=120; fi
if [ "X$MAX_WAIT" = "X" ]  ; then MAX_WAIT=7200; fi
TOTAL_WAIT=0

for dir in $IB_WEEK_DIR ; do
  if [ ! -e ${dir} ] ; then echo "Error: No such directory: ${dir}"; exit 1; fi
done
END_WAIT=NO
while [ true ] ; do
  for proj in cmssw cmssw-patch ; do
    for dir in $IB_WEEK_DIR; do
      if [ -d ${dir}/$ARCH/cms/$proj/$RELEASE ] ; then
        if [ "$END_WAIT" = "YES" ] ; then
          sleep 120
        fi
        exit 0
      fi
    done
  done
  END_WAIT=YES
  if [ $TOTAL_WAIT -gt $MAX_WAIT ] ; then exit 1; fi
  echo "Waiting for IB since ${TOTAL_WAIT} secs"
  sleep $WAIT_STEP
  TOTAL_WAIT=$(expr $TOTAL_WAIT + $WAIT_STEP)
done

