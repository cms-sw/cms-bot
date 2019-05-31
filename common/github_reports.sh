#!/bin/bash -ex

# Functions unique to script
function modify_comment_all_prs() {
    # modify all PR's with message that job has been triggered and add a link to jobs console
    for PR in ${PULL_REQUESTS} ; do
        PR_NAME_AND_REPO=$(echo ${PR} | sed 's/#.*//' )
        PR_NR=$(echo ${PR} | sed 's/.*#//' )
        ${CMS_BOT_DIR}/modify_comment.py -r ${PR_NAME_AND_REPO} -t JENKINS_TEST_URL \
            -m "https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console Started: $(date '+%Y/%m/%d %H:%M')" ${PR_NR} ${DRY_RUN} || true
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
