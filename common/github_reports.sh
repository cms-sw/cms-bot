#!/bin/bash -ex

# Functions unique to script
function modify_comment_all_prs() {
    # modify all PR's with message that job has been triggered and add a link to jobs console
    PR_NAME_AND_REPO=$(echo ${PULL_REQUEST} | sed 's/#.*//' )
    PR_NR=$(echo ${PULL_REQUEST} | sed 's/.*#//' )
    ${CMS_BOT_DIR}/modify_comment.py -r ${PR_NAME_AND_REPO} -t JENKINS_TEST_URL \
        -m "${1}https://cmssdt.cern.ch/${JENKINS_PREFIX}/job/${JOB_NAME}/${BUILD_NUMBER}/console Started: $(date '+%Y/%m/%d %H:%M')" ${PR_NR} ${DRY_RUN} || true
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
      if [ "${TEST_CONTEXT}" != "" ] ; then CONTEXT="${TEST_CONTEXT}/${CONTEXT}" ; fi
      CMSSW_FLAVOR=$(echo $CMSSW_QUEUE | cut -d_ -f4)
      if [ "${CMSSW_FLAVOR}" != "X" ] ; then CONTEXT="${CMSSW_FLAVOR}/${CONTEXT}" ; fi
      if [ "$1" != "" ] ; then CONTEXT="${CONTEXT}/$1" ; fi
    else
      CONTEXT="${COMMIT_STATUS_CONTEXT}"
    fi
    STATE=$2; shift ; shift
    PR_NAME_AND_REPO=$(echo ${PULL_REQUEST} | sed 's/#.*//' )
    PR_NR=$(echo ${PULL_REQUEST} | sed 's/.*#//' )
    if [ -f ${WORKSPACE}/prs_commits.txt ] ; then
        LAST_PR_COMMIT=$(grep "^${PULL_REQUEST}=" $WORKSPACE/prs_commits.txt | sed 's|.*=||;s| ||g')
    else
        LAST_PR_COMMIT=$(cat $(get_path_to_pr_metadata ${PULL_REQUEST})/COMMIT) # get cashed commit hash
    fi
    if [ "$DRY_RUN" = "" -o "${DRY_RUN}" = "false" ] ; then
      mark_commit_status_pr -r "${PR_NAME_AND_REPO}" -c "${LAST_PR_COMMIT}" -C "cms/${CONTEXT}" -s "${STATE}" "$@"
    fi
}

function exit_with_comment_failure_main_pr(){
    # $@ - aditonal options
    # report that job failed to the first PR (that should be our main PR)
    PR_NAME_AND_REPO=$(echo ${PULL_REQUEST} | sed 's/#.*//')
    PR_NR=$(echo ${PULL_REQUEST} | sed 's/.*#//')
    ${CMS_BOT_DIR}/comment-gh-pr -r ${PR_NAME_AND_REPO} -p ${PR_NR} "$@"
    exit 0
}
