#!/bin/bash -ex

IB_WEEK_DIR="/cvmfs/cms-ib.cern.ch/week"
RELEASE=$1
ARCH=$2
WAIT_STEP=$3
MAX_WAIT=$4
if [ "X$RELEASE" = "X" ] ; then echo "Error: Missing release name"     ; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi
if [ "X$ARCH" = "X" ]    ; then echo "Error: Missing architecture name"; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi

if [ "X$WAIT_STEP" = "X" ] ; then WAIT_STEP=120; fi
if [ "X$MAX_WAIT" = "X" ]  ; then MAX_WAIT=7200; fi
TOTAL_WAIT=0

for wk in 0 1 ; do
  if [ ! -e ${IB_WEEK_DIR}$wk ] ; then echo "Error: No such directory: ${IB_WEEK_DIR}$wk"; exit 1; fi
done
while [ true ] ; do
  for wk in 0 1 ; do
    for proj in cmssw cmssw-patch ; do
      if [ -d ${IB_WEEK_DIR}$wk/$ARCH/cms/$proj/$RELEASE ] ; then exit 0 ; fi
    done
  done
  if [ $TOTAL_WAIT -gt $MAX_WAIT ] ; then exit 1; fi
  echo "Waiting for IB since ${TOTAL_WAIT} secs"
  sleep $WAIT_STEP
  TOTAL_WAIT=$(expr $TOTAL_WAIT + $WAIT_STEP)
done

