#!/bin/bash -ex
# Simple small functions that can be reused, but are to small to be their own scripts

WORKSPACE=${WORKSPACE}                # Needs to be exported in master script
CACHED=${WORKSPACE}/CACHED            # Where cached PR metadata etc are kept
BUILD_DIR=testBuildDir
RESULTS_DIR=$WORKSPACE/testsResults
PR_TESTING_DIR=$(dirname $BASH_SOURCE)
export PYTHONUNBUFFERED=1
export CMSBOT_PYTHON_CMD=$(which python3 >/dev/null 2>&1 && echo python3 || echo python)
# -----

function get_cached_GH_JSON (){
    # gives path to cached PR json file
    # if it is the first time a file is requested, it will download it
    PR=$1  # ex. cms-sw/dist#100
    # ---
    REPO=$( echo ${PR} | sed 's/#.*//' )
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    DEST_D=${CACHED}/${REPO}/${PR_NR}
    GH_JSON_PATH=${DEST_D}/GH_JSON.json
    mkdir -p ${DEST_D}
    if  [ ! -f  ${GH_JSON_PATH} ]; then
        # TODO retry if curl fails do to external glitch
        >&2 echo "Downloading PR ${PR}"
        for i in 0 1 2 3 4 ; do
            PYTHONPATH=${PR_TESTING_DIR}/..${PYTHONPATH:+:$PYTHONPATH} ${CMSBOT_PYTHON_CMD} -c "import github_utils,json;data=github_utils.get_pr('${REPO}', '${PR_NR}');print(json.dumps(data))" > ${GH_JSON_PATH} || continue
            echo ${GH_JSON_PATH}
            break
        done
    else
        echo ${GH_JSON_PATH}
    fi
}

function git_clone_and_merge (){
    PR_METADATA_PATH=$1  # Absolute path to JSON format text with PR data from github
    # ---
    BASE_REPO_NAME=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['base']['repo']['name'])")
    BASE_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['base']['ref'])")  # where to merge
    BASE_REPO=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['base']['repo']['full_name'])")

    TEST_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['head']['ref'])")  # PR branch
    TEST_REPO=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['head']['repo']['full_name'])")

    pushd ${WORKSPACE} >/dev/null 2>&1
        if [ $(echo $BASE_REPO | grep '/cmsdist$' | wc -l) -gt 0 ] ; then
          [ ! -z "${CMSDIST_TAG}" ] && BASE_BRANCH="${CMSDIST_TAG}"
        fi
        if  [ ! -d ${BASE_REPO_NAME} ]; then
            git clone https://github.com/${BASE_REPO} -b ${BASE_BRANCH} || git clone git@github.com:${BASE_REPO} -b ${BASE_BRANCH}
        fi
        pushd ${BASE_REPO_NAME}  >/dev/null 2>&1
            git pull --no-rebase https://github.com/${TEST_REPO}.git ${TEST_BRANCH}
        popd
    popd
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    PR_METADATA_PATH=$(get_cached_GH_JSON "$1")
    # echo ${PR_METADATA_PATH}
    EXTERNAL_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys,codecs;obj=json.load(codecs.open('${PR_METADATA_PATH}',encoding='utf-8',errors='ignore'));print(obj['base']['ref'])")
    if [ "${EXTERNAL_BRANCH}" == "" ] ; then exit 1; fi
    echo ${EXTERNAL_BRANCH}
}

function echo_section(){
    echo "---------|  $@  |----------"
}

function prepare_upload_results (){
  pushd $WORKSPACE
    if [ -d ${WORKSPACE}/upload ] ; then
      for ut in $(find $WORKSPACE/upload -mindepth 1 -maxdepth 1 -name '*' -type d | sed 's|.*/||') ; do
        UT_STATUS="OK"
        if [ -f $WORKSPACE/upload/${ut}/status ] ; then UT_STATUS=$(cat $WORKSPACE/upload/${ut}/status) ; fi
        echo "USER_TEST_${ul};${UT_STATUS},User Test ${ut},See Log,${ut}" >> ${RESULTS_DIR}/${ut}.txt
      done
    else
      mkdir -p upload
    fi
    for f in external_checks git-recent-commits.json cmssw.tar.gz unitTests *UnitTests dasqueries testsResults build-logs clang-logs runTheMatrix*-results llvm-analysis *.log *.html *.txt *.js DQMTestsResults valgrindResults-* cfg-viewerResults igprof-results-data git-merge-result git-log-recent-commits addOnTests codeRules dupDict material-budget cmsset_default; do
      [ -e $f ] && mv $f upload/$f
    done
    if [ -e upload/renderPRTests.js ] ; then mkdir -p upload/js && mv upload/renderPRTests.js upload/js/ ; fi
    for f in upload/matrixTests*.log ; do
      if [ -e "$f" ] ; then
        t=$(echo $f | sed 's|.*/matrixTests||;s|.log$||')
        mkdir -p upload/runTheMatrix${t}-results && mv $f upload/runTheMatrix${t}-results/
      fi
    done
    if [ -d upload/addOnTests       ] ; then find upload/addOnTests -name '*.root' -type f | xargs rm -f ; fi
    echo "Preparation done"

    # for uploading CMSDIST build logs
    LOG_SRC="${WORKSPACE}/${BUILD_DIR}/BUILD/${ARCHITECTURE}"
    LOCAL_LOGDIR="${WORKSPACE}/upload"
    if [ -d "${LOG_SRC}" ] ; then
      [ -d ${WORKSPACE}/${BUILD_DIR}/DEPS ] && mv ${WORKSPACE}/${BUILD_DIR}/DEPS ${WORKSPACE}/upload/DEPS
      pushd ${LOG_SRC}
        for dir in $(find . -maxdepth 4 -mindepth 4 -name log -type f | sed 's|/log$||') ; do
          xdir=externals/$(echo $dir | cut -d/ -f3-)
          mkdir -p ${LOCAL_LOGDIR}/${xdir}
          mv ${dir}/log ${LOCAL_LOGDIR}/${xdir}/
          [ -e ${dir}/src-logs.tgz ] && mv ${dir}/src-logs.tgz ${LOCAL_LOGDIR}/${xdir}/
          json=$(basename $(dirname $dir)).json
          [ -e "${dir}/${json}" ] && mv ${dir}/${json} ${LOCAL_LOGDIR}/${xdir}/
          [ -e "${dir}/opts.json" ] && mv ${dir}/opts.json ${LOCAL_LOGDIR}/${xdir}/
        done
      popd
    fi
    if [ -z ${NO_POST} ] ; then
      send_jenkins_artifacts ${WORKSPACE}/upload pull-request-integration/${UPLOAD_UNIQ_ID}
      rm -rf ${WORKSPACE}/upload
      if [ -d ${WORKSPACE}/${CMSSW_VERSION}/das_query ] ; then
        send_jenkins_artifacts ${WORKSPACE}/${CMSSW_VERSION}/das_query das_query/${UPLOAD_UNIQ_ID}/PR || true
        rm -rf ${WORKSPACE}/${CMSSW_VERSION}/das_query
      fi
    fi
    mkdir -p ${RESULTS_DIR}
  popd
}

function is_in_array() {
    local value="$1"
    shift
    local array=("$@")

    for item in "${array[@]}"; do
        if [[ "$item" == "$value" ]]; then
            return 0  # Found match
        fi
    done
    return 1  # No match
}

function get_status_file_name () {
  # get_status_file_name TEST_TYPE TEST_FLAVOR
  [ $# -eq 2 ] || return 1

  TEST_TYPE=$1; shift;
  TEST_FLAVOR=$1; shift;

  UC_TEST_FLAVOR=$(echo "${TEST_FLAVOR}" | tr 'a-z' 'A-Z')

  case $TEST_TYPE in
    relval)
      echo "relval${UC_TEST_FLAVOR}.txt"
      return 0
      ;;
    utest)
      echo "unittest${TEST_FLAVOR}.txt"
      return 0
      ;;
  esac
  return 1
}

function get_result_file_name () {
  # get_result_file_name TEST_TYPE TEST_FLAVOR SUFFIX
  [ $# -eq 3 ] || return 1

  TEST_TYPE=$1; shift;
  TEST_FLAVOR=$1; shift;
  SUFFIX=$1

  UC_TEST_FLAVOR=$(echo "${TEST_FLAVOR}" | tr 'a-z' 'A-Z')

  case $TEST_TYPE in
    relval)
      echo "12${UC_TEST_FLAVOR}-relvals-${SUFFIX}.res"
      return 0
      ;;
    utest)
      echo "14-${TEST_FLAVOR}-${SUFFIX}.res"
      return 0
      ;;
    comp)
      if [ "$TEST_FLAVOR" != "" ]; then
        echo "22-${TEST_FLAVOR}-comparison-report.res"
      else
        echo "20-comparison-report.res"
      fi
      return 0
      ;;
    compnano)
      echo "21-${TEST_FLAVOR}-comparison-report.res"
      return 0
      ;;
  esac
  return 1
}

function get_gpu_matrix_args() {
  OPTS=$(PYTHONPATH=${PR_TESTING_DIR}/.. ${CMSBOT_PYTHON_CMD} -c 'from RelValArgs import GPU_RELVALS_FLAGS;print(GPU_RELVALS_FLAGS)')
  echo ${OPTS}
}
