#!/bin/bash -ex
cd $WORKSPACE
$CMSSW_CVMFS_PATH/../install.sh
export CMSSW_IB=$(basename $CMSSW_CVMFS_PATH)
export CMSSW_VERSION=${CMSSW_IB}
export CMSSW_CVMFS_PATH=""

source $(dirname $0)/setup-pr-test-env.sh
cd $WORKSPACE/${CMSSW_VERSION}
CMSSW_PKG_COUNT=$(ls -d $LOCALRT/src/*/* | wc -l)
REPORT_OPTS="--report-url ${PR_RESULT_URL} $NO_POST"

RESULT_FILE_NAME=$(get_status_file_name utest "$TEST_FLAVOR")
rm -f ${RESULTS_DIR}/${RESULT_FILE_NAME}
mark_commit_status_all_prs "unittests/${TEST_FLAVOR}" 'pending' -u "${BUILD_URL}" -d "Running tests" || true
echo '--------------------------------------'
mkdir -p $WORKSPACE/${TEST_FLAVOR}UnitTests
let UT_TIMEOUT=7200+${CMSSW_PKG_COUNT}*20
gpu_t_lc=$(echo ${TEST_FLAVOR} | tr '[A-Z]' '[a-z]')
if [[ $gpu_t_lc == nvidia_* ]]; then
  gpu_t_lc="cuda"
fi
if [[ $gpu_t_lc == amd_* ]]; then
  gpu_t_lc="rocm"
fi
UTESTS_CMD="USER_UNIT_TESTS=${gpu_t_lc} timeout ${UT_TIMEOUT} scram b -v -k -j ${NCPU}  unittests "
echo "LD_LIBRARY_PATH: ${LD_LIBRARY_PATH}"
scram build echo_LD_LIBRARY_PATH || true
scram build -r echo_CXX || true
cms_major=$(echo ${CMSSW_IB} | cut -d_ -f2)
cms_minor=$(echo ${CMSSW_IB} | cut -d_ -f3)
cms_ver="$(echo 00${cms_major} | sed -E 's|^.*(..)$|\1|')$(echo 00${cms_minor} | sed -E 's|^.*(..)$|\1|')"
echo $UTESTS_CMD > $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt
(eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt 2>&1 || true
echo 'END OF UNIT TESTS'
echo '--------------------------------------'

TEST_ERRORS=$(grep -ai 'had errors\|recipe for target' $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
TEST_ERRORS=`grep -ai "had errors" $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt` || true
GENERAL_ERRORS=`grep -a "ALL_OK" $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt` || true

TEST_FLAVOR_UC=$(echo $TEST_FLAVOR | tr '[:lower:]' '[:upper:]')
REPORT_FILE_NAME=$(get_result_file_name utest "$TEST_FLAVOR" report)
FAILED_FILE_NAME=$(get_result_file_name utest "$TEST_FLAVOR" failed)
if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the ${TEST_FLAVOR} unit tests"
  echo "${TEST_FLAVOR_UC}_UNIT_TEST_RESULTS;ERROR,Unit Tests ${TEST_FLAVOR_UC},See Log,${TEST_FLAVOR}UnitTests" >> ${RESULTS_DIR}/${RESULT_FILE_NAME}
  ALL_OK=false
  UNIT_TESTS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_${TEST_FLAVOR_UC}_UNIT_TESTS_FAIL -f $WORKSPACE/${TEST_FLAVOR}UnitTests/log.txt --report-file ${RESULTS_DIR}/${REPORT_FILE_NAME} ${REPORT_OPTS}
  echo "${TEST_FLAVOR}UnitTests" > ${RESULTS_DIR}/${FAILED_FILE_NAME}
else
  echo "${TEST_FLAVOR_UC}_UNIT_TEST_RESULTS;OK,Unit Tests ${TEST_FLAVOR_UC},See Log,${TEST_FLAVOR}UnitTests" >> ${RESULTS_DIR}/${RESULT_FILE_NAME}
fi
echo "<html><head></head><body>" > $WORKSPACE/${TEST_FLAVOR}UnitTests/success.html
cp $WORKSPACE/${TEST_FLAVOR}UnitTests/success.html $WORKSPACE/${TEST_FLAVOR}UnitTests/failed.html
UT_ERR=false
utlog="testing.log"
for t in $(find $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/src -name ${utlog} -type f | sed "s|$WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/||;s|/${utlog}$||") ; do
  mkdir -p $WORKSPACE/${TEST_FLAVOR}UnitTests/${t}
  mv $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/${t}/${utlog} $WORKSPACE/${TEST_FLAVOR}UnitTests/${t}/
  if [ $(grep -a '^\-\-\-> test  *[^ ]*  *succeeded$' $WORKSPACE/${TEST_FLAVOR}UnitTests/${t}/${utlog} | wc -l) -gt 0 ] ; then
    echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/${TEST_FLAVOR}UnitTests/success.html
  else
    echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/${TEST_FLAVOR}UnitTests/failed.html
    UT_ERR=true
  fi
done
if ! $UT_ERR ; then echo "No unit test failed" >> $WORKSPACE/${TEST_FLAVOR}UnitTests/failed.html ; fi
echo "</body></html>" >> $WORKSPACE/${TEST_FLAVOR}UnitTests/success.html
echo "</body></html>" >> $WORKSPACE/${TEST_FLAVOR}UnitTests/failed.html
prepare_upload_results
if $UNIT_TESTS_OK ; then
  mark_commit_status_all_prs "unittests/${TEST_FLAVOR}" 'success' -u "${BUILD_URL}" -d "Passed"
else
  mark_commit_status_all_prs "unittests/${TEST_FLAVOR}" 'error' -u "${BUILD_URL}" -d "Some unit tests were failed."
fi
