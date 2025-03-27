#!/bin/bash -ex
source ${CMS_BOT_DIR}/jenkins-artifacts
source ${CMS_BOT_DIR}/pr_testing/_helper_functions.sh
rm -f *.prop

if [ "X${UPLOAD_UNIQUE_ID}" = "X" ] ; then exit 0 ; fi
if [ "X${PULL_REQUEST}" = "X" ] ; then exit 0 ; fi

REPOSITORY=$(echo ${PULL_REQUEST} | cut -d '#' -f 1)
PR_ID=$(echo ${PULL_REQUEST} | cut -d '#' -f 2)

COMMIT_ID=$(grep ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/prs_commits.txt -e "^${PULL_REQUEST}=")
if [ "X${COMMIT_ID}" = "X" ] ; then exit 0 ; fi

${CMS_BOT_DIR}/update-commit-statuses-matching.py -r ${REPOSITORY} -c ${COMMIT_ID} -p ${CONTEXT} ${TEST_FLAVOR}

touch abort-jenkins-job.prop
echo "JENKINS_PROJECT_TO_KILL=${JENKINS_PROJECT_TO_KILL}" >> abort-jenkins-job.prop
echo "JENKINS_PROJECT_PARAMS=${JENKINS_PROJECT_PARAMS}" >> abort-jenkins-job.prop
echo "EXTRA_PARAMS=${EXTRA_PARAMS}" >> abort-jenkins-job.prop

###########################################################
UC_TEST_FLAVOR=$(echo "${TEST_FLAVOR}" | tr 'a-z' 'A-Z')

echo "MATRIX${UC_TEST_FLAVOR}_TESTS;ERROR,Matrix ${UC_TEST_FLAVOR} Tests Outputs,Timed out waiting for node,none" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/$(get_status_file_name relval "${TEST_FLAVOR}")
echo "RelVals-${UC_TEST_FLAVOR}" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/$(get_result_file_name relval "${TEST_FLAVOR}" failed)
echo "${TEST_FLAVOR}_UNIT_TEST_RESULTS;ERROR,${UC_TEST_FLAVOR} GPU Unit Tests,Timed out waiting for node,none" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/$(get_status_file_name utest "${TEST_FLAVOR}")
echo "${TEST_FLAVOR}UnitTests" > ${ARTIFACT_BASE_DIR_MAIN}/pull-request-integration/${UPLOAD_UNIQUE_ID}/testsResults/$(get_result_file_name utest "${TEST_FLAVOR}" failed)
