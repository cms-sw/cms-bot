#!/bin/bash -ex
# gets repo name, then returns spec name depending on the rule
PKG_REPO=$1
PKG_NAME=$(echo ${PKG_REPO} | sed 's|.*/||')
ARRAY=(
#   Array of packages to keep track of
#   "REPO_NAME:SPECK_NAME"
    "cms-externals/llvm-project:llvm"
    "cms-sw/SCRAM:SCRAMV1"
    "cms-externals/incubator-mxnet:mxnet-predict"
    "cms-externals/eigen-git-mirror:eigen"
    "cms-externals/tensorflow:tensorflow-sources"
    "HLS_arbitrary_Precision_Types:hls"
    "cms-sw/cmssw-config:coral"
    "cms-externals/dxr:py3-dxr"
    )

case ${PKG_REPO} in
  cms-data/*)
    RECIPE_NAME="data-${PKG_NAME}"
  ;;
  *)
    RECIPE_NAME=${PKG_NAME}
    for repo in "${ARRAY[@]}" ; do
        KEY=${repo%%:*}
        VALUE=${repo#*:}
        if [ "${KEY}" == "${PKG_REPO}" ]; then
            RECIPE_NAME=${VALUE}
        fi
    done
  ;;
esac

echo ${RECIPE_NAME}
