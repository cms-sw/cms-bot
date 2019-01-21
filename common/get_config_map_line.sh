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

# TODO if  CMS_DIST_TAG and  RELEASE_QUEUE are empty, use release $RELEASE_QUEUE=master

CMS_BOT_DIR=$(dirname $(dirname $0))
CONFIG_MAP=${CMS_BOT_DIR}/config.map

#Checked if variables are passed
if [[ -z "$RELEASE_QUEUE" && -z "$CMS_DIST_TAG"  ]]; then
    >&2 echo "ERROR: either RELEASE_QUEUE or CMS_DIST_TAG must be given."
    exit 1
fi

if [[ "$RELEASE_QUEUE" == "master" ]] ; then
    RELEASE_QUEUE=$(grep '^ *CMSSW_DEVEL_BRANCH *= *' ${CMS_BOT_DIR}/releases.py | sed 's/.*= *//;s/"//g;s/ //g'  )
fi

ARCH_MATCH=$(formatFilter 'SCRAM_ARCH' "${ARCHITECTURE}")
CMS_SW_TAG_MATCH=$(formatFilter 'RELEASE_QUEUE' ${RELEASE_QUEUE})
CMSDIST_TAG_MATCH=$(formatFilter 'CMSDIST_TAG' ${CMS_DIST_TAG})

FILTERED_LINES=$(cat ${CONFIG_MAP} | grep -v '^ *#' | grep -v 'NO_IB=' | grep -v 'DISABLED=1;' | grep ${CMS_SW_TAG_MATCH} | grep ${CMSDIST_TAG_MATCH} | grep ${ARCH_MATCH} | tr '\n' '#' )
if [ $(echo "${FILTERED_LINES}" | tr '#' '\n' | grep -c "$ARCH_MATCH" ) -gt 1 ] ; then
  # There should be only 1 production architecture
  FILTERED_LINES=$(echo ${FILTERED_LINES} | tr '#' '\n' | grep 'PROD_ARCH=1' )
  if [ $(echo ${FILTERED_LINES} | tr '#' '\n' | grep -c "$ARCH_MATCH" ) -eq 0 ] ; then
    # If it is not production architecture, there should be only 1 more PR_TEST line
    FILTERED_LINES=$(echo ${FILTERED_LINES} | tr '#' '\n' | grep 'PR_TESTS=1' )
  fi
fi

if [ $(echo ${FILTERED_LINES} | tr '#' '\n' | grep -c "$ARCH_MATCH" ) -ne 1 ] ; then
    >&2 echo "ERROR: No unique match exist."
    exit 1
fi

# we deleted `#` and ignore the last empty line
echo "${FILTERED_LINES}" | tr '#' '\n' | head -1