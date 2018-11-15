#!/bin/bash -ex
# Echos metadata of PR taken from github. It also caches it in specific location
# ---
CMS_BOT_DIR=$(dirname $(dirname $0))  # To get CMS_BOT dir path
WORKSPACE=${CMS_BOT_DIR}/../
CACHED_GH=${WORKSPACE}/CACHED_GH
PR=$1  # ex. cms-sw/dist#100
# ---

REPO=$( echo ${PR} | sed 's/#.*//' )
PR=$(echo ${PR} | sed 's/.*#//')
DEST_D=${CACHED_GH}/${REPO}/${PR}/
GH_JSON=${DEST_D}/GH_JSON.json
mkdir -p ${DEST_D}
if ! [ -f  ${GH_JSON} ]; then
    # TODO retry if curl fails do to external glitch
    curl -s https://api.github.com/repos/${REPO}/pulls/${PR} > ${GH_JSON}
fi
cat ${GH_JSON}