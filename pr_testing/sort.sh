#!/bin/bash -ex

CMS_BOT_DIR=$(dirname $(dirname $0)) # To get CMS_BOT dir path
PR_TESTING_DIR=${CMS_BOT_DIR}/pr_testing
WORKSPACE=${CMS_BOT_DIR}/../
CACHED_GH=$WORKSPACE/CACHED_GH

function fail_if_empty(){
    if [ -z "$1" ]; then
        >&2 echo "ERROR: empty parameter"
        exit 1
    fi
}

function get_base_branch(){
    # get branch to which to merge
    REPO=$( echo $1 | sed 's/#.*//' )
    PR=$(echo $1 | sed 's/.*#//')
    EXTERNAL_BRANCH=$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh $1 | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')
    fail_if_empty ${EXTERNAL_BRANCH}
    echo ${EXTERNAL_BRANCH}
}


#PULL_REQUESTS="cms-sw/root#122,cms-sw/root#126,cms-sw/cmssw#24918,cms-sw/cmsdist#4432,cms-sw/cmssw#24918,cms-sw/root#1222,cms-sw/cmsdist#4432s,cms-sw/cmsdist#4432"
#PULL_REQUESTS="cms-sw/cmsdist#4378,cms-sw/cmsdist#4479,cms-sw/cmsdist#4405"
#PULL_REQUESTS="cms-sw/cmsdist#4479"

PULL_REQUESTS="cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116" # Same branch PR
#PULL_REQUESTS="cms-sw/root#116" # Same branch PR


PULL_REQUESTS=$(echo $PULL_REQUESTS | sed 's/ //g' | tr ',' ' ')
UNIQ_REPOS=$(echo $PULL_REQUESTS |  tr ' ' '\n'  | sed 's|#.*||g' | sort | uniq | tr '\n' ' ' )
fail_if_empty "${UNIQ_REPOS}"
export IFS=" "
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
    for PR in ${FILTERED_PRS}; do
        GH_JSON="$(${PR_TESTING_DIR}/get_cached_GH_JSON.sh ${PR})"
        ${PR_TESTING_DIR}/git_clone_and_merge.sh "${GH_JSON}"
    done
done

echo "DONE"