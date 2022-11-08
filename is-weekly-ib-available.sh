#!/bin/bash -ex

# This script waits until IB is available on CVMFS for future processing. 
# It basicly loops over to see if selected directory is accesable.
# If it is greater then $MAX_WAIT, it will exit with error code.
RELEASE=$1
ARCH=$2
WAIT_STEP=$3
MAX_WAIT=$4
CMS_ARCH=$(echo $ARCH | cut -d_ -f2)
[ "${CMS_ARCH}" != "amd64" ] || CMS_ARCH="x86_64"
if [ "X$RELEASE" = "X" ] ; then echo "Error: Missing release name"     ; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi
if [ "X$ARCH" = "X" ]    ; then echo "Error: Missing architecture name"; echo "Usage: $0 RELEASE ARCH [WAIT_STEP: default 120s] [MAX_WAIT: default 7200s]"; exit 1;  fi

IB_WEEK_DIR="/cvmfs/cms-ib.cern.ch/sw/${CMS_ARCH}/week0 /cvmfs/cms-ib.cern.ch/${CMS_ARCH}/week1 /cvmfs/cms.cern.ch"
if [ "${RELEASE_INSTALL_PATH}" != "" ] ; then IB_WEEK_DIR="${RELEASE_INSTALL_PATH}"; fi
if [ "X$WAIT_STEP" = "X" ] ; then WAIT_STEP=120; fi
if [ "X$MAX_WAIT" = "X" ]  ; then MAX_WAIT=7200; fi
TOTAL_WAIT=0
hostname
for dir in /cvmfs/cms-ib.cern.ch /cvmfs/grid.cern.ch /cvmfs/unpacked.cern.ch ; do
  ls ${dir} >/dev/null || true
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
