#!/bin/bash -ex

CMS_BOT_DIR=$(dirname $(dirname $0)) # To get CMS_BOT dir path
WORKSPACE=../${CMS_BOT_DIR}
CACHED_GH=$WORKSPACE/CACHED_GH

function fail_if_PR_not_found(){
    if [ -z "$1" ]; then
        >&2 echo "ERROR: external pull request not found"
        exit 1
    fi
}

function get_cached_GH_JSON(){
    REPO=$( echo $1 | sed 's/#.*//' )
    PR=$(echo $1 | sed 's/.*#//')
    mkdir -p ${CACHED_GH}/${REPO}
    DEST=${CACHED_GH}/${REPO}/GH_JSON.json
    if [ -f  ${DEST} ]; then
        curl -s https://api.github.com/repos/${REPO}/pulls/${PR} > ${DEST}
    fi
    cat ${DEST}
}

function get_base_branch(){
    # get branch to which to merge
    REPO=$( echo $1 | sed 's/#.*//' )
    PR=$(echo $1 | sed 's/.*#//')
    GH_JSON=$(curl -s https://api.github.com/repos/${REPO}/pulls/${PR})  # PR metadata
    EXTERNAL_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')
    fail_if_PR_not_found $EXTERNAL_BRANCH
    echo ${EXTERNAL_BRANCH}
}

to_newLine() { while read data; do echo "G:$data" | tr ',' '\n' ; done; }

get_cached_GH_JSON


#PULL_REQUESTS="cms-sw/root#122,cms-sw/root#126,cms-sw/cmssw#24918,cms-sw/cmsdist#4432,cms-sw/cmssw#24918,cms-sw/root#1222,cms-sw/cmsdist#4432s,cms-sw/cmsdist#4432"
PULL_REQUESTS="cms-sw/cmsdist#4378,cms-sw/cmsdist#4479,cms-sw/cmsdist#4405"
#PULL_REQUESTS="cms-sw/cmsdist#4479"


PULL_REQUESTS=$(echo $PULL_REQUESTS | sed 's/ //g' | tr ',' ' ')
UNIQ_REPOS="$(echo $PULL_REQUESTS |  tr ',' '\n'  | sed 's/#.*//' | sort | uniq | tr "\n" " " )"
export IFS=" "
for U_REPO in ${UNIQ_REPOS}; do
    FILTERED_PRS=$(echo $PULL_REQUESTS | tr ' ' '\n' | grep $U_REPO | tr '\n' ' ' )
    for PR in ${FILTERED_PRS}; do
        MASTER_LIST="${MASTER_LIST} $(get_base_branch ${PR})"
    done
    NUMBER_U_M=$(echo ${MASTER_LIST} | tr ' ' '\n' | sort | uniq | wc -l)
    if ! [ $NUMBER_U_M  -eq 1 ]; then
        >&2 echo "ERROR: external pull request not found"
    fi

done

