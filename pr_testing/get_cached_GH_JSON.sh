#!/bin/bash -ex
# Caches metadata about PR and gives absolute paths to file
# ---
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )
CACHED=${WORKSPACE}/CACHED

PR=$1  # ex. cms-sw/dist#100
# ---

REPO=$( echo ${PR} | sed 's/#.*//' )
PR=$(echo ${PR} | sed 's/.*#//')
DEST_D=${CACHED}/${REPO}/${PR}
GH_JSON_PATH=${DEST_D}/GH_JSON.json
mkdir -p ${DEST_D}
if  [ ! -f  ${GH_JSON_PATH} ]; then
    # TODO retry if curl fails do to external glitch
    curl -s https://api.github.com/repos/${REPO}/pulls/${PR} > ${GH_JSON_PATH}
    >&2 echo "Downloading PR ${PR}"
    >&2 cat ${GH_JSON_PATH}  # cat for debugging
fi
echo ${GH_JSON_PATH}