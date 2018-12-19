#!/bin/bash -ex
# Takes GH_json as input and then clones base repo and merge PR into it
# ---
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )
CACHED=${WORKSPACE}/CACHED            # Where cached PR metada etc are kept

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
        git pull --rebase git://github.com/${TEST_REPO}.git ${TEST_BRANCH}
    popd
popd