#!/bin/sh -ex
# This script will parse config.map and give back 1 matching line based on search criteria
# Otherwise it will fail.

function formatFilter {
   if [ "X$2" != "X" ]; then
    echo "$1=$2;"
   else
    echo "$1="
   fi
}

CMS_SW_TAG=$1
CMS_DIST_TAG=$2
ARCHITECTURE=$3

CMS_BOT_DIR=$(dirname $(dirname $0))
CONFIG_MAP=${CMS_BOT_DIR}/config.map

#Checked if variables are passed
if [[ -z "$CMS_SW_TAG" && -z "$CMS_DIST_TAG"  ]]; then
    >&2 echo "ERROR: either CMS_SW_TAG or CMS_DIST_TAG must be given."
    exit 1
fi

ARCH_MATCH=$(formatFilter 'SCRAM_ARCH' ${ARCHITECTURE})
CMS_SW_TAG_MATCH=$(formatFilter 'RELEASE_QUEUE' ${CMS_SW_TAG})
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