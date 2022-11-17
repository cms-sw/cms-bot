#!/bin/bash -ex
# Simple small functions that can be reused, but are to small to be their own scripts

WORKSPACE=${WORKSPACE}                # Needs to be exported in master script
CACHED=${WORKSPACE}/CACHED            # Where cached PR metadata etc are kept
BUILD_DIR=testBuildDir
RESULTS_DIR=$WORKSPACE/testsResults
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
            curl -s https://api.github.com/repos/${REPO}/pulls/${PR_NR} > ${GH_JSON_PATH} || continue
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
    BASE_REPO_NAME=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['base']['repo']['name'])")
    BASE_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['base']['ref'])")  # where to merge
    BASE_REPO=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['base']['repo']['full_name'])")

    TEST_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['head']['ref'])")  # PR branch
    TEST_REPO=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['head']['repo']['full_name'])")

    pushd ${WORKSPACE} >/dev/null 2>&1
        if [ $(echo $BASE_REPO | grep '/cmsdist$' | wc -l) -gt 0 ] ; then
          [ ! -z "${CMSDIST_TAG}" ] && BASE_BRANCH="${CMSDIST_TAG}"
        fi
        if  [ ! -d ${BASE_REPO_NAME} ]; then
            git clone https://github.com/${BASE_REPO} -b ${BASE_BRANCH} || git clone git@github.com:${BASE_REPO} -b ${BASE_BRANCH}
        fi
        pushd ${BASE_REPO_NAME}  >/dev/null 2>&1
            git pull https://github.com/${TEST_REPO}.git ${TEST_BRANCH}
        popd
    popd
}

function get_base_branch(){
    # get branch to which to merge from GH PR json
    PR_METADATA_PATH=$(get_cached_GH_JSON "$1")
    # echo ${PR_METADATA_PATH}
    EXTERNAL_BRANCH=$(${CMSBOT_PYTHON_CMD} -c "import json,sys;obj=json.load(open('${PR_METADATA_PATH}'));print(obj['base']['ref'])")
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
    for f in external_checks git-recent-commits.json cmssw.tar.gz unitTests dasqueries testsResults build-logs clang-logs runTheMatrix*-results llvm-analysis *.log *.html *.txt *.js DQMTestsResults valgrindResults-* cfg-viewerResults igprof-results-data git-merge-result git-log-recent-commits addOnTests CRABTests-* codeRules dupDict material-budget ; do
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
        for log in $(find . -maxdepth 4 -mindepth 4 -name log -type f | sed 's|^./||') ; do
          dir=$(dirname $log)
          mkdir -p ${LOCAL_LOGDIR}/${dir}
          mv $log ${LOCAL_LOGDIR}/${dir}/
          [ -e ${dir}/src-logs.tgz ] && mv ${dir}/src-logs.tgz ${LOCAL_LOGDIR}/${dir}/
          json=$(basename $(dirname $dir)).json
          [ -e "${dir}/${json}" ] && mv ${dir}/${json} ${LOCAL_LOGDIR}/${dir}/
          [ -e "${dir}/opts.json" ] && mv ${dir}/opts.json ${LOCAL_LOGDIR}/${dir}/
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
