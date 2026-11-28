#!/bin/bash -ex
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

# Runs the L1T DPG orchestrator pipeline on CERN GitLab (container build,
# NanoAOD production, analysis) for a cmssw PR and waits for its result.
# It is run on demand: "enable l1t_dpg".
#
# The commit status context is under opt/ : a failed pipeline is shown in the
# PR test results, but it does not make cms-bot reject the PR tests.

# Settings, the Jenkins job can override any of them
L1T_DPG_GITLAB_URL="${L1T_DPG_GITLAB_URL:-https://gitlab.cern.ch}"
L1T_DPG_GITLAB_PROJECT="${L1T_DPG_GITLAB_PROJECT:-cms-analysis/l1t-dpg/orchestrator}"
L1T_DPG_GITLAB_REF="${L1T_DPG_GITLAB_REF:-main}"
# EOS area the pipeline writes to. Each test gets its own sub-directory
L1T_DPG_EOS_BASE_DIR="${L1T_DPG_EOS_BASE_DIR:-}"
# Seconds to wait for the pipeline, which normally needs 1 to 3 hours, and between two checks of its status
L1T_DPG_TIMEOUT="${L1T_DPG_TIMEOUT:-14400}"
L1T_DPG_POLL="${L1T_DPG_POLL:-60}"
# File with the pipeline trigger token of the GitLab project
L1T_DPG_TRIGGER_TOKEN="${L1T_DPG_TRIGGER_TOKEN:-/data/secrets/l1t-dpg-trigger-token}"
# File with a GitLab access token to read the pipeline status, as used by
# jenkins-jobs/git/git-mirror-repository.py. If there is no such file then
# the pipelines of the GitLab project have to be public
GITLAB_SECRET_TOKEN="${GITLAB_SECRET_TOKEN:-/data/secrets/cmsbuild-gitlab-secret}"

L1T_DPG_CONTEXT="opt/l1t-dpg"
L1T_DPG_LOG="${WORKSPACE}/l1t-dpg.log"
L1T_DPG_RES="ERROR"
L1T_DPG_DESC=""
L1T_DPG_REPORTED=false
PIPELINE_JSON="${WORKSPACE}/l1t-dpg-pipeline.json"
PIPELINE_URL=""
EOS_DIR=""

# cms-bot waits for as long as a commit status is pending: never leave it like that
function l1t_dpg_on_exit () {
  if ! ${L1T_DPG_REPORTED} ; then
    mark_commit_status_all_prs "${L1T_DPG_CONTEXT}" 'error' -u "${BUILD_URL}" -d "L1T DPG test ended unexpectedly"
  fi
}
trap l1t_dpg_on_exit EXIT

function gitlab_pipeline () {
  # Run it outside of the CMSSW environment, like mark_commit_status_pr does
  (eval `scram unset -sh` ; ${CMS_BOT_DIR}/gitlab-pipeline.py -u "${L1T_DPG_GITLAB_URL}" -p "${L1T_DPG_GITLAB_PROJECT}" -o "${PIPELINE_JSON}" "$@") 2>&1 | tee -a ${L1T_DPG_LOG}
  return ${PIPESTATUS[0]}
}

# Report test started
mark_commit_status_all_prs "${L1T_DPG_CONTEXT}" 'pending' -u "${BUILD_URL}" -d "Running"

# The pipeline builds the PR branch itself: find the repository and branch of the cmssw PR
CMSSW_PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep '^cms-sw/cmssw#' | head -1)
HEAD_REPO=""
HEAD_REF=""
if [ "${CMSSW_PR}" != "" ] ; then
  PR_JSON=$(eval `scram unset -sh` ; get_cached_GH_JSON "${CMSSW_PR}")
  if [ "${PR_JSON}" != "" ] ; then
    HEAD_REPO=$(${CMSBOT_PYTHON_CMD} -c "import json,codecs;obj=json.load(codecs.open('${PR_JSON}',encoding='utf-8',errors='ignore'));print(obj['head']['repo']['full_name'])" || true)
    HEAD_REF=$(${CMSBOT_PYTHON_CMD} -c "import json,codecs;obj=json.load(codecs.open('${PR_JSON}',encoding='utf-8',errors='ignore'));print(obj['head']['ref'])" || true)
  fi
fi

# The repository and branch names are chosen by the author of the PR and they end up
# in the variables of a pipeline which builds and runs that branch: only accept plain names
if [[ ! "${HEAD_REPO}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || [[ ! "${HEAD_REF}" =~ ^[A-Za-z0-9_./-]+$ ]] ; then
  L1T_DPG_DESC="Unable to find a usable branch for the cmssw PR"
elif [ "${L1T_DPG_EOS_BASE_DIR}" = "" ] ; then
  L1T_DPG_DESC="L1T_DPG_EOS_BASE_DIR is not set"
else
  EOS_DIR="${L1T_DPG_EOS_BASE_DIR}/PR-$(echo ${CMSSW_PR} | sed 's|.*#||')/${BUILD_NUMBER}"
  RC=0
  gitlab_pipeline -t "${L1T_DPG_TRIGGER_TOKEN}" -r "${L1T_DPG_GITLAB_REF}" \
    -v "CMSSW_RELEASE=${CMSSW_VERSION}" \
    -v "CMSSW_FORK_URL=https://github.com/${HEAD_REPO}/tree/${HEAD_REF}" \
    -v "EOS_BASE_DIR=${EOS_DIR}" || RC=$?
  if [ $RC -ne 0 ] ; then
    L1T_DPG_DESC="Unable to trigger the GitLab pipeline"
  else
    PIPELINE_ID=$(${CMSBOT_PYTHON_CMD} -c "import json;print(json.load(open('${PIPELINE_JSON}'))['id'])")
    PIPELINE_URL=$(${CMSBOT_PYTHON_CMD} -c "import json;print(json.load(open('${PIPELINE_JSON}'))['web_url'])")
    mark_commit_status_all_prs "${L1T_DPG_CONTEXT}" 'pending' -u "${PIPELINE_URL}" -d "GitLab pipeline ${PIPELINE_ID} is running"
    API_TOKEN_OPTS=""
    if [ -f "${GITLAB_SECRET_TOKEN}" ] ; then API_TOKEN_OPTS="-a ${GITLAB_SECRET_TOKEN} --cancel-on-abort" ; fi
    RC=0
    gitlab_pipeline -i ${PIPELINE_ID} -w --timeout ${L1T_DPG_TIMEOUT} --poll ${L1T_DPG_POLL} ${API_TOKEN_OPTS} || RC=$?
    case $RC in
      0 ) L1T_DPG_RES="SUCCESS" ; L1T_DPG_DESC="GitLab pipeline succeeded" ;;
      3 ) L1T_DPG_DESC="GitLab pipeline failed" ;;
      4 ) L1T_DPG_DESC="GitLab pipeline did not finish within ${L1T_DPG_TIMEOUT}s" ;;
      * ) L1T_DPG_DESC="Unable to get the result of the GitLab pipeline" ;;
    esac
  fi
fi
echo "${L1T_DPG_DESC}" >> ${L1T_DPG_LOG}

# Results for the PR summary. Nothing is added to the failed tests: this test is informative only
touch ${RESULTS_DIR}/11-l1t-dpg-report.res ${RESULTS_DIR}/11-l1t-dpg-failed.res
if [ "${PIPELINE_URL}" != "" ] ; then
  echo "L1T_DPG;${L1T_DPG_RES},L1T DPG GitLab pipeline,See pipeline,${PIPELINE_URL}" >> ${RESULTS_DIR}/l1t-dpg.txt
  echo "L1T_DPG_LOG;OK,L1T DPG GitLab pipeline log,See Log,l1t-dpg.log" >> ${RESULTS_DIR}/l1t-dpg.txt
  echo "**L1T DPG**: ${L1T_DPG_DESC}, see the [pipeline](${PIPELINE_URL}). Output: \`${EOS_DIR}\`" > ${RESULTS_DIR}/11-l1t-dpg-report.res
else
  echo "L1T_DPG;ERROR,L1T DPG GitLab pipeline,See Log,l1t-dpg.log" >> ${RESULTS_DIR}/l1t-dpg.txt
  echo "**L1T DPG**: ${L1T_DPG_DESC}" > ${RESULTS_DIR}/11-l1t-dpg-report.res
fi

# Upload the results before the final commit status: cms-bot reads them as soon as no status is pending
rm -f ${PIPELINE_JSON}
prepare_upload_results

if [ "${L1T_DPG_RES}" = "SUCCESS" ] ; then
  mark_commit_status_all_prs "${L1T_DPG_CONTEXT}" 'success' -u "${PIPELINE_URL}" -d "${L1T_DPG_DESC}"
else
  mark_commit_status_all_prs "${L1T_DPG_CONTEXT}" 'error' -u "${PIPELINE_URL:-${BUILD_URL}}" -d "${L1T_DPG_DESC}"
fi
L1T_DPG_REPORTED=true
