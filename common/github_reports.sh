#!/bin/bash -ex

if [ "${CONTEXT_PREFIX}" = "" ] ; then CONTEXT_PREFIX="cms"; fi

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
      CONTEXT="${ARCHITECTURE}"
      CMSSW_FLAVOR=$(echo $CMSSW_QUEUE | cut -d_ -f4)
      if [ "${CMSSW_FLAVOR}" != "X" ] ; then CONTEXT="${CMSSW_FLAVOR}/${CONTEXT}" ; fi
      if [ "$1" != "" ] ; then CONTEXT="${CONTEXT}/$1" ; fi
    else
      CONTEXT="${COMMIT_STATUS_CONTEXT}"
    fi
    STATE=$2; shift ; shift
    PR_NAME_AND_REPO=$(echo ${PULL_REQUEST} | sed 's/#.*//' )
    PR_NR=$(echo ${PULL_REQUEST} | sed 's/.*#//' )
    LAST_PR_COMMIT=$(grep "^${PULL_REQUEST}=" $WORKSPACE/prs_commits | sed 's|.*=||;s| ||g')
    if [ "X$LAST_PR_COMMIT" = "X" ]; then
      LAST_PR_COMMIT = ${ENV_LAST_PR_COMMIT}
    fi
    if [ "$DRY_RUN" = "" -o "${DRY_RUN}" = "false" ] ; then
      mark_commit_status_pr -r "${PR_NAME_AND_REPO}" -c "${LAST_PR_COMMIT}" -C "${CONTEXT_PREFIX}/${CONTEXT}" -s "${STATE}" "$@"
    fi
}
