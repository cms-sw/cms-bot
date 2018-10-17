#!/usr/bin/env bash
# set -x
PKG_NAME=$1 #package name from variable
ARCH=slc6_amd64_gcc700

if [ -z "$1" ]; then
    echo "PKG name not set"
    exit 1
fi

SOURCES=$(./pkgtools/cmsBuild -c cmsdist/ -a $ARCH -i temp_build/ -j 8 --no-bootstrap --sources  build  $PKG_NAME | \
            grep -i "^$PKG_NAME:source=" | grep https://github.com/ )
N=$(echo $SOURCES | grep -cve '^\s*$' )
echo "Number of sources: " $N
echo "Sources:"
echo $SOURCES

if [ $N -eq 0 ]; then
   echo "External sources not found"
   exit 1
elif [ $N -eq 1 ]; then
   echo "One source found"
else
   echo "More then one external source is found"
   exit 1
fi

OUTPUT=$(echo $SOURCES  | sed 's/ .*//' | sed 's/&.*//')
# PKG_NAME=$( echo $OUTPUT | sed 's/:.*//')
SOURCE_NAME=$(echo $OUTPUT | sed 's/.*://' | sed 's/=.*//')
DIR_NAME=$(echo $OUTPUT | sed 's/.*=//')

echo "--source $PKG_NAME:$SOURCE_NAME=$(pwd)/$DIR_NAME" > get_source_flag_result.txt