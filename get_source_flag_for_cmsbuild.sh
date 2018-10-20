#!/usr/bin/env bash

# This script will be us by jenkins job (TODO INSERT JOB HERE)
# It will generate --sources flag for pkgtools/build.py script
#
# $EXTERNAL_REPO - Github repo if the external
# $EXTERNAL_PR - pull request number
# $CMS_SW_TAG - CMS SW TAG found in config_map.py

# TODO - not all packages have matching repo name with project name
# We should create a map in cmsdist for such pacakges

EXTERNAL_REPO=$1
EXTERNAL_PR=$2
CMS_SW_TAG=$3
ARCH=slc6_amd64_gcc700 # Hardcode since cmsbuild always needs an architecture
PKG_TOOL_BRANCH="V00-32-DEVEL"
BUILD_DIR="testBuildDir"

#Checked if variables are passed
if [[ -z "$1" || -z "$2" || -z "$3" ]]; then
    echo "empty parameters"
    echo "EXTERNAL_REPO: '${EXTERNAL_REPO}', EXTERNAL_PR: '${EXTERNAL_PR}', CMS_SW_TAG: '${CMS_SW_TAG}'"
    exit 1
fi

PKG_NAME=$(echo ${EXTERNAL_REPO} | sed 's|.*/||') # package name from variable
GH_JSON=$(curl -s https://api.github.com/repos/${EXTERNAL_REPO}/pulls/${EXTERNAL_PR})

if [ $( echo $GH_JSON | grep -c '"message": "Not Found"' ) -eq 1 ]; then
    echo "ERROR: external pull request not found"
    exit 1
fi

# TEST_USER=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["repo"]["owner"]["login"]')
TEST_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["head"]["ref"]')
TEST_REPO=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["repo"]["full_name"]')
EXTERNAL_BRANCH=$(echo $GH_JSON | python -c 'import json,sys;obj=json.load(sys.stdin);print obj["base"]["ref"]')

git clone https://github.com/${EXTERNAL_REPO} ${PKG_NAME} -b ${EXTERNAL_BRANCH}
pushd ${PKG_NAME}
    git pull git://github.com/${TEST_REPO}.git ${TEST_BRANCH}
    rm -rf .git
popd

#find correct CMS_DIST_TAG
FILTERED_CONF=$(cat cms-bot/config.map | grep -i ${CMS_SW_TAG} | grep -v DISABLED=1)
if [ $(echo ${FILTERED_CONF} | grep -c -i ${CMS_SW_TAG}) -ne 1 ]; then
    FILTERED_CONF=$(echo ${FILTERED_CONF} | grep  PROD_ARCH=1 )
    if [ $(echo ${FILTERED_CONF} | grep -c -i ${CMS_SW_TAG}) -ne 1 ]; then
        echo "ERROR: Could not match correct CMSDIST_TAG"
        exit 1
    fi
fi

CMSDIST_BRANCH=$(echo ${FILTERED_CONF} | sed 's/^.*CMSDIST_TAG=//' | sed 's/;.*//' )
ARCH=$(echo ${FILTERED_CONF} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )

git clone -b ${CMSDIST_BRANCH} https://github.com/cms-sw/cmsdist.git
git clone -b ${PKG_TOOL_BRANCH} https://github.com/cms-sw/pkgtools.git

./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME}

SOURCES=$(./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME} | \
                        grep -i "^${PKG_NAME}:source" | grep github.com/${EXTERNAL_REPO} )

N=$(echo ${SOURCES} | grep -cve '^\s*$' )
echo "Number of sources: " ${N}
echo "Sources:"
echo ${SOURCES}

if [ ${N} -eq 0 ]; then
   echo "ERROR: External sources not found"
   exit 1
elif [ ${N} -eq 1 ]; then
   echo "One source found"
else
   echo "ERROR: More then one external source is found"
   exit 1
fi

OUTPUT=$(echo ${SOURCES}  | sed 's/ .*//' )
# PKG_NAME=$( echo ${OUTPUT} | sed 's/:.*//')
SOURCE_NAME=$(echo ${OUTPUT} | sed 's/.*://' | sed 's/=.*//')
DIR_NAME=$(echo ${OUTPUT} | sed 's/.*=//')

# move external to new place
if [ ${PKG_NAME} != ${DIR_NAME} ]; then
    mv ${PKG_NAME} ${DIR_NAME}
fi
# Output result
echo "--source ${PKG_NAME}:${SOURCE_NAME}=$(pwd)/${DIR_NAME}" > get_source_flag_result.txt