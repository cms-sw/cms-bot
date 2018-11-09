#!/bin/bash -ex

# This script will be us by jenkins job (https://cmssdt.cern.ch/jenkins/job/ib-any-integration)
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
ARCH=$4
# PKG_TOOL_BRANCH
BUILD_DIR="testBuildDir"

CMS_BOT_DIR=$(dirname $(dirname $0)) # To get CMS_BOT dir path

#Checked if variables are passed
if [[ -z "$1" || -z "$2" || -z "$3" ]]; then
    >&2 echo "empty parameters"
    >&2 echo "EXTERNAL_REPO: '${EXTERNAL_REPO}', EXTERNAL_PR: '${EXTERNAL_PR}', CMS_SW_TAG: '${CMS_SW_TAG}'"
    exit 1
fi

PKG_NAME=$(echo ${EXTERNAL_REPO} | sed 's|.*/||') # package name from variable
GH_JSON=$(curl -s https://api.github.com/repos/${EXTERNAL_REPO}/pulls/${EXTERNAL_PR})

if [ $( echo $GH_JSON | grep -c '"message": "Not Found"' ) -eq 1 ]; then
    >&2 echo "ERROR: external pull request not found"
    >&2 echo 1
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

FILTERED_CONF=$(${CMS_BOT_DIR}/common/get_config_map_line.sh "${CMS_SW_TAG}" "" "${ARCH}" )
CMSDIST_BRANCH=$(echo ${FILTERED_CONF} | sed 's/^.*CMSDIST_TAG=//' | sed 's/;.*//' )
if [[ -z ${ARCH} ]] ; then
  ARCH=$(echo ${FILTERED_CONF} | sed 's/^.*SCRAM_ARCH=//' | sed 's/;.*//' )
fi
PKG_TOOL_BRANCH=$(echo ${FILTERED_CONF} | sed 's/^.*PKGTOOLS_TAG=//' | sed 's/;.*//' )

if ! [ -d "cmsdist" ]; then
    git clone --depth 1 -b ${CMSDIST_BRANCH} https://github.com/cms-sw/cmsdist.git
fi


if ! [ -d "pkgtools" ]; then
    git clone --depth 1 -b ${PKG_TOOL_BRANCH} https://github.com/cms-sw/pkgtools.git
fi



./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME}

SOURCES=$(./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME} | \
                        grep -i "^${PKG_NAME}:source" | grep github.com/${EXTERNAL_REPO} | tr '\n' '#' )

N=$(echo ${SOURCES} | tr '#' '\n' | grep -ci ':source' )
echo "Number of sources: " ${N}
echo "Sources:"
echo ${SOURCES}

if [ ${N} -eq 0 ]; then
   >&2 echo "ERROR: External sources not found"
   exit 1
elif [ ${N} -eq 1 ]; then
   echo "One source found"
else
   >&2 echo  "ERROR: More then one external source is found"
   exit 1
fi

OUTPUT=$(echo ${SOURCES}  | sed 's/ .*//' | tr '#' '\n' )
# PKG_NAME=$( echo ${OUTPUT} | sed 's/:.*//')
SOURCE_NAME=$(echo ${OUTPUT} | sed 's/.*://' | sed 's/=.*//')
DIR_NAME=$(echo ${OUTPUT} | sed 's/.*=//')

# Move to other path
OUT_PATH=$RANDOM
mv PKG_NAME ${OUT_PATH}/${DIR_NAME}
echo "--source ${PKG_NAME}:${SOURCE_NAME}=$(pwd)/${OUT_PATH}/${DIR_NAME}" >> get_source_flag_result.txt
