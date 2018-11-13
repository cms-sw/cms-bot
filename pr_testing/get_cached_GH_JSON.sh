#!/bin/bash -ex

CMS_BOT_DIR=$(dirname $(dirname $0)) # To get CMS_BOT dir path
WORKSPACE=${CMS_BOT_DIR}/../
CACHED_GH=$WORKSPACE/CACHED_GH
# ----

REPO=$( echo $1 | sed 's/#.*//' )
PR=$(echo $1 | sed 's/.*#//')
DEST_D=${CACHED_GH}/${REPO}/${PR}/
GH_JSON=${DEST_D}/GH_JSON.json
mkdir -p ${DEST_D}
if ! [ -f  ${GH_JSON} ]; then
    # TODO retry if curl fails do to external glitch
    curl -s https://api.github.com/repos/${REPO}/pulls/${PR} > ${GH_JSON}
fi
cat ${GH_JSON}