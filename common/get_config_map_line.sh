#!/bin/bash -ex
# This script will parse config.map and give back 1 matching line based on search criteria
# Otherwise it will fail.

function formatFilter {
   if [ "X$2" != "X" ]; then
    echo "$1=$2;"
   else
    echo "$1="
   fi
}

RELEASE_QUEUE=$1
CMS_DIST_TAG=$2
ARCHITECTURE=$3
CMS_BOT_DIR=$(dirname $(dirname $0))
CONFIG_MAP=${CMS_BOT_DIR}/config.map

#Checked if variables are passed
if [[ -z "$RELEASE_QUEUE" && -z "$CMS_DIST_TAG"  ]]; then
    >&2 echo "WARNING: both RELEASE_QUEUE and CMS_DIST_TAG empty, setting RELEASE_QUEUE to master."
    RELEASE_QUEUE='master'
fi
if [[ "$RELEASE_QUEUE" == "master" ]] ; then
    RELEASE_QUEUE=$(curl -s -L https://cmssdt.cern.ch/SDT/BaselineDevRelease | grep '^CMSSW_')
    if [[ -z "$RELEASE_QUEUE" ]] ; then
        RELEASE_QUEUE=$(grep '^ *CMSSW_DEVEL_BRANCH *= *' ${CMS_BOT_DIR}/releases.py | sed 's/.*= *//;s/"//g;s/ //g'  )
    fi
fi
ARCH_MATCH=$(formatFilter 'SCRAM_ARCH' "${ARCHITECTURE}")
CMS_SW_TAG_MATCH=$(formatFilter 'RELEASE_QUEUE' "${RELEASE_QUEUE}")
CMSDIST_TAG_MATCH=$(formatFilter 'CMSDIST_TAG' "${CMS_DIST_TAG}")

FILTERED_LINES=$(cat ${CONFIG_MAP} | grep -v '^ *#' | grep -v 'NO_IB=' | grep -v 'DISABLED=1;' | grep ${CMS_SW_TAG_MATCH} | grep ${CMSDIST_TAG_MATCH} | grep ${ARCH_MATCH} | tr '\n' '#' )
F_L_NUMBER=$(echo "${FILTERED_LINES}" | tr '#' '\n' | grep -c "$ARCH_MATCH" ) || true

if [[ ${F_L_NUMBER} -eq 0 && ! -z ${CMS_DIST_TAG} ]]; then
  # if no match, we drop `grep ${CMS_SW_TAG_MATCH}` part and rely on `CMSDIST_TAG_MATCH`
  FILTERED_LINES=$(cat ${CONFIG_MAP} | grep -v '^ *#' | grep -v 'NO_IB=' | grep -v 'DISABLED=1;' | grep ${CMSDIST_TAG_MATCH} | grep ${ARCH_MATCH} | tr '\n' '#' )
  F_L_NUMBER=$(echo "${FILTERED_LINES}" | tr '#' '\n' | grep -c "$ARCH_MATCH" ) || true
fi

SUB_FILTERED_LINES=${FILTERED_LINES}
if [ ${F_L_NUMBER} -gt 1 ] ; then
  # There should be only 1 production architecture
  SUB_FILTERED_LINES=$(echo ${FILTERED_LINES} | tr '#' '\n' | grep 'PROD_ARCH=1' | tr '\n' '#')
  if [ $(echo ${SUB_FILTERED_LINES} | tr '#' '\n' | grep -c "$ARCH_MATCH" ) -eq 0 ] ; then
    # If it is not production architecture, there should be only 1 more PR_TEST line
    SUB_FILTERED_LINES=$(echo ${FILTERED_LINES} | tr '#' '\n' | grep 'PR_TESTS=1' | tr '\n' '#')
  fi
fi

if [ $(echo ${SUB_FILTERED_LINES} | tr '#' '\n' | grep -c "$ARCH_MATCH" ) -ne 1 ] ; then
    >&2 echo "ERROR: No unique match exist."
    exit 1
fi

# we deleted `#` and ignore the last empty line
echo "${SUB_FILTERED_LINES}" | tr '#' '\n' | head -1

