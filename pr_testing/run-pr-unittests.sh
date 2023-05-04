#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh
cd $WORKSPACE/${CMSSW_VERSION}
CMSSW_PKG_COUNT=$(ls -d $LOCALRT/src/*/* | wc -l)

rm -f ${RESULTS_DIR}/unittestGPU.txt
mark_commit_status_all_prs 'unittests/gpu' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
echo '--------------------------------------'
mkdir -p $WORKSPACE/gpuUnitTests
let UT_TIMEOUT=7200+${CMSSW_PKG_COUNT}*20
UTESTS_CMD="USER_UNIT_TESTS=cuda timeout ${UT_TIMEOUT} scram b -v -k -j ${NCPU}  runtests "
echo "LD_LIBRARY_PATH: ${LD_LIBRARY_PATH}"
scram build echo_LD_LIBRARY_PATH || true
cms_major=$(echo ${CMSSW_IB} | cut -d_ -f2)
cms_minor=$(echo ${CMSSW_IB} | cut -d_ -f3)
cms_ver="$(echo 00${cms_major} | sed -E 's|^.*(..)$|\1|')$(echo 00${cms_minor} | sed -E 's|^.*(..)$|\1|')"
echo $UTESTS_CMD > $WORKSPACE/gpuUnitTests/log.txt
(eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/gpuUnitTests/log.txt 2>&1 || true
exit 1
echo 'END OF UNIT TESTS'
echo '--------------------------------------'

TEST_ERRORS=$(grep -ai 'had errors\|recipe for target' $WORKSPACE/gpuUnitTests/log.txt | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
TEST_ERRORS=`grep -ai "had errors" $WORKSPACE/gpuUnitTests/log.txt` || true
GENERAL_ERRORS=`grep -a "ALL_OK" $WORKSPACE/gpuUnitTests/log.txt` || true

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the gpu unit tests"
  echo 'GPU_UNIT_TEST_RESULTS;ERROR,Unit Tests,See Log,gpuUnitTests' >> ${RESULTS_DIR}/unittestGPU.txt
  ALL_OK=false
  UNIT_TESTS_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_UNIT_TESTS_FAIL -f $WORKSPACE/gpuUnitTests/log.txt --report-file ${RESULTS_DIR}/14-unittestGPU-report.res ${REPORT_OPTS}
  echo "UnitTests" > ${RESULTS_DIR}/14-failed.res
else
  echo 'GPU_UNIT_TEST_RESULTS;OK,GPU Unit Tests,See Log,gpuUnitTests' >> ${RESULTS_DIR}/unittestGPU.txt
fi
echo "<html><head></head><body>" > $WORKSPACE/gpuUnitTests/success.html
cp $WORKSPACE/gpuUnitTests/success.html $WORKSPACE/gpuUnitTests/failed.html
UT_ERR=false
utlog="testing.log"
for t in $(find $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/src -name ${utlog} -type f | sed "s|$WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/||;s|/${utlog}$||") ; do
  mkdir -p $WORKSPACE/gpuUnitTests/${t}
  mv $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/${t}/${utlog} $WORKSPACE/gpuUnitTests/${t}/
  if [ $(grep -a '^\-\-\-> test  *[^ ]*  *succeeded$' $WORKSPACE/gpuUnitTests/${t}/${utlog} | wc -l) -gt 0 ] ; then
    echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/gpuUnitTests/success.html
  else
    echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/gpuUnitTests/failed.html
    UT_ERR=true
  fi
done
if ! $UT_ERR ; then echo "No unit test failed" >> $WORKSPACE/gpuUnitTests/failed.html ; fi
echo "</body></html>" >> $WORKSPACE/gpuUnitTests/success.html
echo "</body></html>" >> $WORKSPACE/gpuUnitTests/failed.html
prepare_upload_results
if $UNIT_TESTS_OK ; then
  mark_commit_status_all_prs 'unittest/gpu' 'success' -u "${BUILD_URL}" -d "Passed"
else
  mark_commit_status_all_prs 'unittest/gpu' 'error' -u "${BUILD_URL}" -d "Some unit tests were failed."
fi
