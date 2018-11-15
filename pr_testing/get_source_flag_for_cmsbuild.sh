#!/bin/bash -ex
# This script will be us by jenkins job (https://cmssdt.cern.ch/jenkins/job/ib-any-integration)
# It will generate --sources flag for pkgtools/build.py script and move package to specific directory
# TODO - not all packages have matching repo name with project name
# TODO We should create a map in cmsdist for such pacakges
# ---
SCRIPTPATH="$( cd "$(dirname "$0")" ; pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
WORKSPACE=$(dirname ${CMS_BOT_DIR} )
CACHED=${WORKSPACE}/CACHED

PKG_REPO=$1       # Repo of external (ex. cms-sw/root)
PKG_NAME=$2       # Name of external (ex. root)
CMS_SW_TAG=$3     # CMS SW TAG found in config_map.py
ARCH=$4
BUILD_DIR="testBuildDir"  # Where pkgtools/cmsBuild builds software
# ---

# Checked if variables are passed
if [[ -z "$PKG_REPO" || -z "$PKG_NAME" || -z "$CMS_SW_TAG" ]]; then
    >&2 echo "empty parameters"
    >&2 echo "EXTERNAL_REPO: '${PKG_REPO}', PKG_NAME: '${PKG_NAME}', CMS_SW_TAG: '${CMS_SW_TAG}'"
    exit 1
fi

pushd ${WORKSPACE}
pushd ${PKG_NAME}
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
    # TODO check branch
fi

if ! [ -d "pkgtools" ]; then
    git clone --depth 1 -b ${PKG_TOOL_BRANCH} https://github.com/cms-sw/pkgtools.git
fi

./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME}
SOURCES=$(./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i ${BUILD_DIR} -j 8 --sources --no-bootstrap build  ${PKG_NAME} | \
                        grep -i "^${PKG_NAME}:source" | grep github.com/${PKG_REPO} | tr '\n' '#' )

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
SOURCE_NAME=$(echo ${OUTPUT} | sed 's/.*://' | sed 's/=.*//')
DIR_NAME=$(echo ${OUTPUT} | sed 's/.*=//')

# Move to other path
OUT_PATH=${RANDOM}
mkdir ${OUT_PATH}
mv ${PKG_NAME} ${OUT_PATH}/${DIR_NAME}
echo "--source ${PKG_NAME}:${SOURCE_NAME}=$(pwd)/${OUT_PATH}/${DIR_NAME}" >> get_source_flag_result.txt

popd # ${WORKSPACE}