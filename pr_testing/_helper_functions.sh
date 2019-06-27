#!/bin/bash -ex
# Simple small functions that can be reused, but are to small to be their own scripts

WORKSPACE=${WORKSPACE}                # Needs to be exported in master script
CACHED=${WORKSPACE}/CACHED            # Where cached PR metadata etc are kept
# -----

function get_path_to_pr_metadata(){
    PR=$1  # ex. cms-sw/dist#100
    # ---
    REPO=$( echo ${PR} | sed 's/#.*//' )
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    DEST_D=${CACHED}/${REPO}/${PR_NR}
    echo ${DEST_D}
}

function get_cached_GH_JSON (){
    # gives path to cached PR json file
    # if it is the first time a file is requested, it will download it
    PR=$1  # ex. cms-sw/dist#100
    # ---
    REPO=$( echo ${PR} | sed 's/#.*//' )
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    DEST_D=${CACHED}/${REPO}/${PR_NR}
    GH_JSON_PATH=${DEST_D}/GH_JSON.json
    mkdir -p ${DEST_D}
    if  [ ! -f  ${GH_JSON_PATH} ]; then
        # TODO retry if curl fails do to external glitch
        curl -s https://api.github.com/repos/${REPO}/pulls/${PR_NR} > ${GH_JSON_PATH}
        >&2 echo "Downloading PR ${PR}"
        >&2 cat ${GH_JSON_PATH}  # cat for debugging
    fi
    echo ${GH_JSON_PATH}
}

function git_clone_and_merge (){
    PR_METADATA_PATH=$1  # Absolute path to JSON format text with PR data from github
    # ---
    BASE_REPO_NAME=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['repo']['name']")
    BASE_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")  # where to merge
    BASE_REPO=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['repo']['full_name']")

    TEST_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['head']['ref']")  # PR branch
    TEST_REPO=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['head']['repo']['full_name']")

    pushd ${WORKSPACE}
        if  [ ! -d ${BASE_REPO_NAME} ]; then
            git clone https://github.com/${BASE_REPO} -b ${BASE_BRANCH}
        fi
        pushd ${BASE_REPO_NAME}
            git pull  git://github.com/${TEST_REPO}.git ${TEST_BRANCH}
        popd
    popd
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    PR_METADATA_PATH=$(get_cached_GH_JSON "$1")
    # echo ${PR_METADATA_PATH}
    EXTERNAL_BRANCH=$(python -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print obj['base']['ref']")
    fail_if_empty "${EXTERNAL_BRANCH}" "PR had errors - ${1}"
    echo ${EXTERNAL_BRANCH}
}

function echo_section(){
    echo "---------|  $@  |----------"
}

function fail_if_empty(){
    if [ -z $(echo "$1" | tr -d ' ' ) ]; then
        exit_with_comment_failure_main_pr -m "ERROR: empty variable. ${2}." ${DRY_RUN} || true
        exit 1
    fi
}


