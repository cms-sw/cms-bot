#!/bin/bash -ex
# This script should check if there are cms-bot PR and merge into current repo
# Kept as a minimum to avoid chicken and egg problem
# ---
# Constants
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})             # To get CMS_BOT dir path
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
source ${PR_TESTING_DIR}/_helper_functions.sh    # general helper functions

PULL_REQUESTS=$1
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | tr ',' ' ' | sed 's/  */ /g' | sed 's/^ *//;s/ *$//' )  # to make consistent separation in list
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )  # Repos without pull number

# Do git pull --rebase for only /cms-bot
for U_REPO in $(echo ${UNIQ_REPOS} | tr ' ' '\n'  | grep '/cms-bot' ); do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        git_clone_and_merge "$(get_cached_GH_JSON "${PR}")"
    done
done

