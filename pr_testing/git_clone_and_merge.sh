#!/bin/bash -ex

# Takes GH_json as input and then clones and merges repos
# ---

CMS_BOT_DIR=$(dirname $(dirname $0)) # To get CMS_BOT dir path
WORKSPACE=${CMS_BOT_DIR}/../
CACHED_GH=${WORKSPACE}/CACHED_GH
# ---

GH_JSON=$1

# TEST_USER=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["owner"]["login"]')
BASE_REPO_NAME=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["repo"]["name"]')
BASE_BRANCH=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')  # where to merge
BASE_REPO=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["repo"]["full_name"]')

TEST_BRANCH=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["ref"]')  # PR branch
TEST_REPO=$(echo ${GH_JSON} | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["full_name"]')

pushd ${WORKSPACE}
    if  [ ! -d ${BASE_REPO_NAME} ]; then
        git clone https://github.com/${BASE_REPO} -b ${BASE_BRANCH}
    fi
    pushd ${BASE_REPO_NAME}
        git pull --rebase git://github.com/${TEST_REPO}.git ${TEST_BRANCH}
    popd
popd