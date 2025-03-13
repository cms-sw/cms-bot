#!/bin/bash -ex
source ${CMS_BOT_DIR}/jenkins-artifacts
rm -f *.prop

if [ "X${UPLOAD_UNIQUE_ID}" = "X" ] ; then exit 0 ; fi
if [ "X${PULL_REQUEST}" = "X" ] ; then exit 0 ; fi

REPOSITORY=$(echo ${PULL_REQUEST} | cut -d '#' -f 1)
PR_ID=$(echo ${PULL_REQUEST} | cut -d '#' -f 2)

COMMIT_ID=$(grep ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/prs_commits.txt -e "^${PULL_REQUEST}=")
if [ "X${COMMIT_ID}" = "X" ] ; then exit 0 ; fi

${CMS_BOT_DIR}/update-commit-statuses-matching.py -r ${REPOSITORY} -c ${COMMIT_ID} -p ${CONTEXT} rocm

touch abort-jenkins-job.prop
echo "JENKINS_PROJECT_TO_KILL=${JENKINS_PROJECT_TO_KILL}" >> abort-jenkins-job.prop
echo "JENKINS_PROJECT_PARAMS=${JENKINS_PROJECT_PARAMS}" >> abort-jenkins-job.prop
echo "EXTRA_PARAMS=${EXTRA_PARAMS}" >> abort-jenkins-job.prop

echo "MATRIXROCM_TESTS;ERROR,Matrix ROCM Tests Outputs,Timed out waiting for node,none" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/relvalROCM.txt
echo "RelVals-ROCM" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/12ROCM-relvals-failed.res
echo "rocm_UNIT_TEST_RESULTS;ERROR,ROCM GPU Unit Tests,Timed out waiting for node,none" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/unittestrocm.txt
echo "rocmUnitTests" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/14-failed.res
