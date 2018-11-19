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
CMS_SW_TAG=$2           # CMS SW TAG found in config_map.py
ARCHITECTURE=$3             # architecture (ex. slc6_amd64_gcc700)
# ---

function fail_if_empty(){
    if [ -z "$1" ]; then
        ERROR_MESSAGE=$2
        >&2 echo "ERROR: empty parameter, ${2}"
        exit 1
    fi
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    PR_METADATA_PATH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "$1")
    echo ${PR_METADATA_PATH}
    EXTERNAL_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
    fail_if_empty "${EXTERNAL_BRANCH}" "PR had errors - ${1}"
    echo ${EXTERNAL_BRANCH}
}

# -- MAIN --
PULL_REQUESTS=$(echo ${PULL_REQUESTS} | sed 's/ //g' | tr ',' ' ')
UNIQ_REPOS=$(echo ${PULL_REQUESTS} |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )
fail_if_empty "${UNIQ_REPOS}" "There was no unique repos"
UNIQ_REPO_NAMES=$(echo ${UNIQ_REPOS} | tr ' ' '\n' | sed 's|.*/||' )
UNIQ_REPO_NAMES_WITH_COUNT=$(echo ${UNIQ_REPO_NAMES} | sort | uniq -c )

# Check if same organization/repo PRs
if [ $(echo $UNIQ_REPO_NAMES_WITH_COUNT  | grep -v '1 ' | wc -w ) -gt 0 ]; then
    >&2 echo "ERROR: multiple PRs from different organisations but same repos:"
    >$2 echo $UNIQ_REPO_NAMES_WITH_COUNT
    exit 1
fi
FILTERED_CONF=$(${CMS_BOT_DIR}/common/get_config_map_line.sh "${CMS_SW_TAG}" "" "${ARCHITECTURE}" )
PKG_TOOL_BRANCH=$(echo ${FILTERED_CONF} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )
PKG_TOOL_VERSION=$(echo ${PKG_TOOL_BRANCH} | cut -d- -f 2)
if [[ ${PKG_TOOL_VERSION} -lt 32 && ! -z $(echo ${UNIQ_REPO_NAMES} |  tr ' ' '\n' | grep -v -w cmssw | grep -v -w cmsdist ) ]] ; then
    >&2 echo "ERROR: CMS_SW_TG ${CMS_SW_TAG} uses PKG_TOOL_BRANCH ${PKG_TOOL_BRANCH} which is lower then required to test externals."
    exit 1
fi

# Filter PR for specific repo and then check if its PRs point to same base branch
for U_REPO in ${UNIQ_REPOS}; do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ' )
    MASTER_LIST=""
    for PR in ${FILTERED_PRS}; do
        MASTER_LIST="${MASTER_LIST} $(get_base_branch ${PR})"
    done
    UNIQ_MASTERS=$(echo ${MASTER_LIST} | tr ' ' '\n' | sort | uniq )
    if [ -z ${UNIQ_MASTERS} ]; then continue ; fi
    NUMBER_U_M=$(echo ${UNIQ_MASTERS} | wc -l )
    if  [ ! ${NUMBER_U_M}  -eq 1 ]; then
        >&2 echo "ERROR: PRs for  repo '${U_REPO}' wants to merge to different branches: ${UNIQ_MASTERS}"
        exit 1
    fi
done

# Do git pull --rebase for each PR
for U_REPO in $(echo ${UNIQ_REPOS} | tr ' ' '\n'  | grep -v '/cmssw' ); do
    FILTERED_PRS=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep ${U_REPO} | tr '\n' ' ')
    for PR in ${FILTERED_PRS}; do
        ${PR_TESTING_DIR}/git_clone_and_merge.sh "$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh "${PR}")"
    done
done

# Preparations depending on from repo type
for U_REPO in ${UNIQ_REPOS}; do
    PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
    PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
    case "$PKG_NAME" in  # We do not care where the repo is kept (ex. cmssw organisation or other)
		cmssw)
			PULL_REQUEST=$(echo ${PR} | sed 's/.*#//' )
		;;
		cmsdist)
			CMSDIST_PR=$(echo ${PR} | sed 's/.*#//' )
		;;
		*)
		    echo "external"
			PKG_REPO=$(echo ${U_REPO} | sed 's/#.*//')
			PKG_NAME=$(echo ${U_REPO} | sed 's|.*/||')
			${PR_TESTING_DIR}/get_source_flag_for_cmsbuild.sh "$PKG_REPO" "$PKG_NAME" "$CMS_SW_TAG" "$ARCHITECTURE"
		;;
	esac
done