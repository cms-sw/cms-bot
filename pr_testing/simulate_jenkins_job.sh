#!/usr/bin/env bash
# debuging set
export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'
export PYTHONPATH=${PYTHONPATH}:"/cvmfs/cms-ib.cern.ch/jenkins-env/python/shared"

SCRIPTPATH="$( cd "$(dirname "$0")" ; /bin/pwd -P )"  # Absolute path to script
CMS_BOT_DIR=$(dirname ${SCRIPTPATH})  # To get CMS_BOT dir path
# Input variable
export PULL_REQUESTS="gudrutis/root#2, gudrutis/root#3"              # "cms-sw/cmsdist#4488,cms-sw/cmsdist#4480,cms-sw/cmsdist#4479,cms-sw/root#116"
export RELEASE_FORMAT="CMSSW_10_4_ROOT6_X_2018-11-27-2300"             # CMS SW TAG found in config_map.py
export PULL_REQUEST=
export CMSDIST_PR=
export ARCHITECTURE= # architecture (ex. slc6_amd64_gcc700)
# RELEASE_FORMAT=           # RELEASE_QUEUE found in config_map.py (ex. CMSSW_10_4_ROOT6_X )
# DO_TESTS=
# DO_SHORT_MATRIX=
# DO_STATIC_CHECKS=
# DO_DUPLICATE_CHECKS=
# MATRIX_EXTRAS=
# export ADDITIONAL_PULL_REQUESTS=   # aditonal CMSSW PRs
# WORKFLOWS_FOR_VALGRIND_TEST=
export AUTO_POST_MESSAGE=false
# RUN_CONFIG_VIEWER=
# USE_DAS_CACHE=
# BRANCH_NAME=
# APPLY_FIREWORKS_RULE=
# RUN_IGPROF=
# TEST_CLANG_COMPILATION=
# MATRIX_TIMEOUT=
# EXTRA_MATRIX_ARGS=
# DO_ADDON_TESTS=
# RUN_ON_SLAVE=
# COMPARISON_ARCH=
# DISABLE_POISON=
# FULL_TOOLCONF=
export PUB_USER=

export WORKSPACE=
export USER=
export BUILD_NUMBER=999999
export JOB_NAME=

export DRY_RUN=  # No communication with external servers
export BUILD_ALL=  # Build all

EXPORT COPY_STATUS=1

${CMS_BOT_DIR}/pr_testing/test_multiple_prs.sh
