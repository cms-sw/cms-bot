#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

mark_commit_status_all_prs 'addon' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
#Some data files in cmssw_7_1/src directory are newer then cmsswdata. We make sure that we pick up these files from src instead of data.
#Without this hack, pat1 addOnTest fails.
EX_DATA_SEARCH="$CMSSW_SEARCH_PATH"
case $CMSSW_IB in
  XXCMSSW_7_1_* )
    for xdata_pkg in Geometry/CMSCommonData Geometry/ForwardCommonData Geometry/HcalCommonData Geometry/MuonCommonData Geometry/TrackerCommonData ; do
      if [ -e ${CMSSW_BASE}/external/${SCRAM_ARCH}/data/${xdata_pkg}/data ] ; then
        if [ ! -e ${CMSSW_BASE}/src/${xdata_pkg}/data ] ; then
          mkdir -p ${LOCALRT}/xdata/${xdata_pkg}
          ln -s $CMSSW_RELEASE_BASE/src/${xdata_pkg}/data ${LOCALRT}/xdata/${xdata_pkg}/data
          EX_DATA_SEARCH="${LOCALRT}/xdata:$CMSSW_SEARCH_PATH"
        fi
      fi
    done
  ;;
esac
#End of 71x data hack

echo '--------------------------------------'
ADDON_CMD="CMSSW_SEARCH_PATH=$EX_DATA_SEARCH LOCALRT=${WORKSPACE}/${CMSSW_VERSION} timeout 7200 addOnTests.py -j ${NCPU}"
echo $ADDON_CMD > $WORKSPACE/addOnTests.log
STIME=$(date +%s)
(eval $ADDON_CMD && echo 'ALL_OK') 2>&1 | tee -a $WORKSPACE/addOnTests.log
set DTIME=$(date +%s)-$STIME
echo 'END OF ADDON TESTS'
echo '--------------------------------------'
if [ $(grep -a ' tests passed, ' $WORKSPACE/addOnTests.log | wc -l) -eq 0 ] ; then
  echo "AddOnTest might have timed out: FAILED - $DTIME secs" >>  $WORKSPACE/addOnTests.log
fi

TEST_ERRORS=`grep -ai -E ": FAILED .*" $WORKSPACE/addOnTests.log` || true
GENERAL_ERRORS=`grep -a "ALL_OK" $WORKSPACE/addOnTests.log` || true

if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
  echo "Errors in the addOnTests"
  echo 'ADDON_TESTS;ERROR,AddOn Tests,See Logs,addOnTests' >> ${RESULTS_DIR}/adddon.txt
  ALL_OK=false
  ADDON_OK=false
  $CMS_BOT_DIR/report-pull-request-results PARSE_ADDON_FAIL -f $WORKSPACE/addOnTests.log --report-file ${RESULTS_DIR}/13-addon-report.res --report-url ${PR_RESULT_URL}
  echo "AddOn" > ${RESULTS_DIR}/13-addon-failed.res
else
  touch ${RESULTS_DIR}/13-addon-failed.res
  touch ${RESULTS_DIR}/13-addon-report.res
  echo "no errors in the addOnTests!!"
  echo 'ADDON_TESTS;OK,AddOn Tests,See Logs,addOnTests' >> ${RESULTS_DIR}/adddon.txt
fi
prepare_upload_results
if $ADDON_OK ; then
  mark_commit_status_all_prs 'addon' 'success' -u "${BUILD_URL}" -d "Passed"
else
  mark_commit_status_all_prs 'addon' 'error' -u "${BUILD_URL}" -d "Errors in the addOnTests"
fi
