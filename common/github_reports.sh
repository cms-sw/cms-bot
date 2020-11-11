#!/bin/bash -ex

# Functions unique to script
function modify_comment_all_prs() {
    # modify all PR's with message that job has been triggered and add a link to jobs console
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        ${CMS_BOT_DIR}/modify_comment.py -r ${PR_NAME_AND_REPO} -t JENKINS_TEST_URL \
            -m "${1}https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console Started: $(date '+%Y/%m/%d %H:%M')" ${PR_NR} ${DRY_RUN} || true
    done
}

function report_pull_request_results_all_prs() {
    # post message of test status on Github on all PR's
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        ${CMS_BOT_DIR}/report-pull-request-results $@ --repo ${PR_NAME_AND_REPO} --pr ${PR_NR}  # $@ - pass all parameters given to function
    done
}

function report_pull_request_results_all_prs_with_commit() {
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        LAST_PR_COMMIT=$(cat $(get_path_to_pr_metadata ${PR})/COMMIT) # get cashed commit hash
        ${CMS_BOT_DIR}/report-pull-request-results $@ --repo ${PR_NAME_AND_REPO} --pr ${PR_NR} -c ${LAST_PR_COMMIT}
    done
}

function mark_commit_status_pr () {
  local ERR=1
  for i in 0 1 2 3 4 ; do
      if [ "$(eval `scram unset -sh` && ${CMS_BOT_DIR}/mark_commit_status.py "$@" 2>&1 && echo ALL_OK | grep 'ALL_OK' | wc -l)" -gt 0 ]  ; then
          ERR=0
          break
      else
          sleep 10
      fi
  done
  if [ $ERR -gt 0 ] ; then exit $ERR; fi
}

function mark_commit_status_all_prs () {
    if [ "${COMMIT_STATUS_CONTEXT}" = "" ] ; then 
      CONTEXT="${SCRAM_ARCH}"
      CMSSW_FLAVOR=$(echo $CMSSW_QUEUE | cut -d_ -f4)
      if [ "${CMSSW_FLAVOR}" != "X" ] ; then CONTEXT="${CMSSW_FLAVOR}/${CONTEXT}" ; fi
      if [ "$1" != "" ] ; then CONTEXT="${CONTEXT}/$1" ; fi
    else
      CONTEXT="${COMMIT_STATUS_CONTEXT}"
    fi
    STATE=$2; shift ; shift
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        if [ -f ${WORKSPACE}/prs_commits.txt ] ; then
          LAST_PR_COMMIT=$(grep "^${PR}=" $WORKSPACE/prs_commits.txt | sed 's|.*=||;s| ||g')
        else
          LAST_PR_COMMIT=$(cat $(get_path_to_pr_metadata ${PR})/COMMIT) # get cashed commit hash
        fi
        mark_commit_status_pr -r "${PR_NAME_AND_REPO}" -c "${LAST_PR_COMMIT}" -C "cms/${CONTEXT}" -s "${STATE}" "$@"
    done
}

function exit_with_comment_failure_main_pr(){
    # $@ - aditonal options
    # report that job failed to the first PR (that should be our main PR)
    PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep -v '^$' | head -1  ) # get main(first) pr
    PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//')
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    ${CMS_BOT_DIR}/comment-gh-pr -r ${PR_NAME_AND_REPO} -p ${PR_NR} "$@"
    exit 0
}

function exit_with_report_failure_main_pr(){
    # $@ - aditonal options
    # report that job failed to the first PR (that should be our main PR)
    PR=$(echo ${PULL_REQUESTS} | tr ' ' '\n' | grep -v '^$' | head -1  ) # get main(first) pr
    PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//')
    PR_NR=$(echo ${PR} | sed 's/.*#//')
    ${CMS_BOT_DIR}/report-pull-request-results  $@ --repo ${PR_NAME_AND_REPO} --pr ${PR_NR}
    exit 0
}
