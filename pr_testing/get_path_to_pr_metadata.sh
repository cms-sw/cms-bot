#!/bin/bash -ex
# Caches metadata about PR and gives absolute paths to file
# TODO make a function
# ---
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )
CACHED=${WORKSPACE}/CACHED

PR=$1  # ex. cms-sw/dist#100
# ---

REPO=$( echo ${PR} | sed 's/#.*//' )
PR_NR=$(echo ${PR} | sed 's/.*#//')
DEST_D=${CACHED}/${REPO}/${PR_NR}

echo ${DEST_D}