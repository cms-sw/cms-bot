#!/bin/bash -ex
# This script will be called by Jenkins job ( TODO what job)
# and
# 1) will merge multiple PRs for multiple repos
# 2) run tests and post result on github
# ---
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )
CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing

PULL_REQUESTS=$1            # "cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116"
RELEASE_FORMAT=$2           # CMS SW TAG found in config_map.py
ARCHITECTURE=$3             # architecture (ex. slc6_amd64_gcc700)
# ---

function fail_if_empty(){
    if [ -z "$1" ]; then
        >&2 echo "ERROR: empty parameter"
        exit 1
    fi
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    REPO=$( echo $1 | sed 's/#.*//' )
    PR=$(echo $1 | sed 's/.*#//')
    EXTERNAL_BRANCH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh $1 | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')
    fail_if_empty ${EXTERNAL_BRANCH}
    echo ${EXTERNAL_BRANCH}
}

# -- MAIN --
PULL_REQUESTS=$(echo $PULL_REQUESTS | sed 's/ //g' | tr ',' ' ')
UNIQ_REPOS=$(echo $PULL_REQUESTS |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )
fail_if_empty "${UNIQ_REPOS}"
export IFS=" "

# Filter PR for specific repo and then check if its PRs point to same base branch
for U_REPO in ${UNIQ_REPOS}; do
    FILTERED_PRS=$(echo $PULL_REQUESTS | tr ' ' '\n' | grep $U_REPO | tr '\n' ' ' )
    MASTER_LIST=""
    for PR in ${FILTERED_PRS}; do
        MASTER_LIST="${MASTER_LIST} $(get_base_branch ${PR})"
    done
    UNIQ_MASTERS=$(echo ${MASTER_LIST} | tr ' ' '\n' | sort | uniq )
    if [ -z ${UNIQ_MASTERS} ]; then continue ; fi
    NUMBER_U_M=$(echo ${UNIQ_MASTERS} | wc -l )
    if  [ ! $NUMBER_U_M  -eq 1 ]; then
        >&2 echo "ERROR: PRs for  repo '${U_REPO}' wants to merge to different branches: ${UNIQ_MASTERS}"
        exit 1
    fi
done

# Do git pull --rebase for each PR
for U_REPO in ${UNIQ_REPOS}; do
    FILTERED_PRS=$(echo $PULL_REQUESTS | tr ' ' '\n' | grep $U_REPO | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        GH_JSON="$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh ${PR})"
        ${PR_TESTING_DIR}/git_clone_and_merge.sh "${GH_JSON}"
    done
done

# Preparations depending on from repo type
for U_REPO in ${UNIQ_REPOS}; do
    case "$U_REPO" in
		cms-sw/cmssw)
			PULL_REQUEST=$(echo ${PR} | sed 's/.*#//' )
		;;
		cms-sw/cmsdist)
			CMSDIST_PR=$(echo ${PR} | sed 's/.*#//' )
		;;
		*)
		    echo "external"
			PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
			PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
			${PR_TESTING_DIR}/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$PKG_NAME" "$RELEASE_FORMAT" "$ARCHITECTURE"
		;;
	esac
done