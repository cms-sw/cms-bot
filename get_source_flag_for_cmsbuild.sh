#!/usr/bin/env bash

# This script will be us be jenkins job (TODO INSERT JOB HERE)
# It will generate
#
# $EXTERNAL_REPO - Github repo if the external
# $EXTERNAL_PR - pull request number
# $CMS_SW_TAG - CMS SW TAG found in config_map.py

set -x # TODO remove


EXTERNAL_REPO=$1
EXTERNAL_PR=$2
CMS_SW_TAG=$3

ARCH=slc6_amd64_gcc700 # Hardcode since cmsbuild always needs an architecture
PKG_TOOL_BRANCH="V00-32-DEVEL" # TODO for development


if [[ -z "$1" && -z "$2" && -z "$3" ]]; then
    echo "empty parameters"
    echo "EXTERNAL_REPO: '${EXTERNAL_PR}', EXTERNAL_PR: '${EXTERNAL_PR}', CMS_SW_TAG: '${CMS_SW_TAG}'"
    exit 1
fi

# TODO check if external, pr, and tag are not mallformed
PKG_NAME=$(echo ${EXTERNAL_PR} | sed 's|.*/||') #package name from variable

GH_JSON=$(curl -s https://api.github.com/repos/${EXTERNAL_REPO}/pulls/${EXTERNAL_PR})
if [ $( echo $GH_JSON | grep -c '"message": "Not Found"' ) -eq 1 ]; then
    echo "external pull reguest not found"
    exit 1
fi


# TODO clone external to new directory
git clone https://github.com/${EXTERNAL_PR}

PKG_TOOL_BRANCH # TODO should specify branch, need to use config.py

git clone -b ${CMSDIST_BRANCH} https://github.com/cms-sw/cmsdist.git
git clone -b ${PKG_TOOL_BRANCH} https://github.com/cms-sw/pkgtools.git

SOURCES=$(./pkgtools/cmsBuild -c cmsdist/ -a ${ARCH} -i temp_build/ -j 8 --no-bootstrap --sources  build  ${PKG_NAME} | \
            grep -i "^${PKG_NAME}:source=" | grep https://github.com/ )

N=$(echo ${SOURCES} | grep -cve '^\s*$' )
echo "Number of sources: " ${N}
echo "Sources:"
echo ${SOURCES}

if [ ${N} -eq 0 ]; then
   echo "External sources not found"
   exit 1
elif [ ${N} -eq 1 ]; then
   echo "One source found"
else
   echo "More then one external source is found"
   exit 1
fi

OUTPUT=$(echo ${SOURCES}  | sed 's/ .*//' | sed 's/&.*//')
# PKG_NAME=$( echo ${OUTPUT} | sed 's/:.*//')
SOURCE_NAME=$(echo ${OUTPUT} | sed 's/.*://' | sed 's/=.*//')
DIR_NAME=$(echo ${OUTPUT} | sed 's/.*=//')

# move external to new place
mv ${PKG_NAME} ${DIR_NAME}

# Output result
echo "--source ${PKG_NAME}:${SOURCE_NAME}=$(pwd)/${DIR_NAME}" > get_source_flag_result.txt

# cleanup
rm -rf temp_build