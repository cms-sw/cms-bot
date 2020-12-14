#!/bin/bash -ex
source $WORKSPACE/job.env
cd $WORKSPACE/$CMSSW_IB

#Copy the cmssw ib das_client wrapper in PATH
cp -f $CMS_BOT_DIR/das-utils/das_client $CMS_BOT_DIR/das-utils/das_client.py
set +x ; eval $(scram run -sh) ;set -x

#Drop RELEASE_TOP/external/SCRAM_ARCH/data if LOCALTOP/external/SCRAM_ARCH/data exists
#to make sure external packages removed files are not picked up from release directory
if $BUILD_EXTERNAL ; then
  if [ "X${CMSSW_RELEASE_BASE}" != "X" ] ; then
    export CMSSW_SEARCH_PATH=$(echo $CMSSW_SEARCH_PATH | tr ':' '\n'  | grep -v "$CMSSW_RELEASE_BASE/external/" | tr '\n' ':')
  fi
fi
export PATH=$CMS_BOT_DIR/das-utils:$PATH
[ "X$USE_DAS_SORT" = "XYES" ] && $CMS_BOT_DIR/das-utils/use-ibeos-sort


#Duplicate dict
QA_RES="NOTRUN"
if [ "X$DO_DUPLICATE_CHECKS" = Xtrue -a "X$CMSDIST_ONLY" == "Xfalse" ]; then
  mkdir $WORKSPACE/dupDict
  QA_RES="OK"
  for type in dup lostDefs edmPD ; do
    duplicateReflexLibrarySearch.py --${type} 2>&1 | grep -v ' SKIPPING ' > $WORKSPACE/dupDict/${type}.txt || true
  done
  QA_COUNT=$(cat $WORKSPACE/dupDict/dup.txt | grep '^  *[.]/[A-Z]' | grep '.xml' | sed 's|^  *./||' | sort | uniq | wc -l)
  if [ $QA_COUNT -gt 0 ] ; then QA_RES="ERROR" ; fi
  QA_COUNT=$(cat $WORKSPACE/dupDict/lostDefs.txt | grep '^[.]/[A-Z]' | grep '.xml' | sed 's|^./||' | sort | uniq | wc -l)
  if [ $QA_COUNT -gt 0 ] ; then  QA_RES="ERROR" ; fi
  if [ -s $WORKSPACE/dupDict/edmPD ] ; then QA_RES="ERROR" ; fi
  echo "DUPLICATE_DICT_RULES;${QA_RES},Duplicate Dictionaries,See Logs,dupDict" >> ${RESULTS_DIR}/qa.txt
fi

export CMS_PATH=/cvmfs/cms-ib.cern.ch
#
#Checking runTheMatrix das-queries
#
DAS_QUERY_RES="NOTRUN"
if [ "X$DO_DAS_QUERY" = Xtrue ]; then
  if [ $(runTheMatrix.py --help | grep ibeos | wc -l) -gt 0 ] ; then
    mkdir -p $WORKSPACE/dasqueries/run
    DAS_QUERY_RES="OK"
    pushd $WORKSPACE/dasqueries/run
      $SCRIPTPATH/run-das-query.py > ../run.txt 2>&1 || DAS_QUERY_RES="ERROR"
      if [ -f runall-report-step123-.log ] ; then
        grep 'DAS_ERROR' runall-report-step123-.log > ../failed_workflows.log || true
        mv runall-report-step123-.log ..
        if [ -s ../failed_workflows.log ] ; then
          DAS_QUERY_RES="ERROR"
          echo -e "\n* **DAS Queries**: The DAS query tests failed, see the summary page for details.\n" >> ${RESULTS_DIR}/11-report.res
        fi
      fi
    popd
    rm -rf $WORKSPACE/dasqueries/run
    echo "DAS_QUERIES;${DAS_QUERY_RES},DAS Queries,See Logs,dasqueries" >> ${RESULTS_DIR}/dasqueries.txt
  fi
fi
prepare_upload_results
mkdir -p $WORKSPACE/upload

#
# Unit tests
#
echo 'UNIT_TEST_RESULTS;NOTRUN' > ${RESULTS_DIR}/unittest.txt
if [ "X$DO_TESTS" = Xtrue ]; then
  rm -f ${RESULTS_DIR}/unittest.txt
  mark_commit_status_all_prs 'unittest' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  echo '--------------------------------------'
  mkdir -p $WORKSPACE/unitTests
  UT_TIMEOUT=$(echo 7200+${CMSSW_PKG_COUNT}*20 | bc)
  UTESTS_CMD="timeout ${UT_TIMEOUT} scram b -k -j ${NCPU}  runtests "
  echo $UTESTS_CMD > $WORKSPACE/unitTests/log.txt
  (eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/unitTests/log.txt 2>&1 || true
  echo 'END OF UNIT TESTS'
  echo '--------------------------------------'
  #######################################
  # check if DQM Tests where run
  #######################################
  if ls $WORKSPACE/$CMSSW_IB/src/DQMServices/Components/test/ | grep -v -E "[a-z]+"; then
    echo "DQM Tests were run!"
    pushd $WORKSPACE/$CMSSW_IB/src/DQMServices/Components/test/
    ls | grep -v -E "[a-z]+" | xargs -I ARG mv ARG DQMTestsResults
    mkdir $WORKSPACE/DQMTestsResults
    cp -r DQMTestsResults $WORKSPACE/DQMTestsResults
    ls $WORKSPACE
    popd
    echo 'DQM_TESTS;OK,DQM Unit Tests,See Logs,DQMTestsResults' >> ${RESULTS_DIR}/unittest.txt
  fi

  TEST_ERRORS=$(grep -i 'had errors\|recipe for target' $WORKSPACE/unitTests/log.txt | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
  TEST_ERRORS=`grep -i "had errors" $WORKSPACE/unitTests/log.txt` || true
  GENERAL_ERRORS=`grep "ALL_OK" $WORKSPACE/unitTests/log.txt` || true

  if [ "X$TEST_ERRORS" != "X" -o "X$GENERAL_ERRORS" = "X" ]; then
    echo "Errors in the unit tests"
    echo 'UNIT_TEST_RESULTS;ERROR,Unit Tests,See Log,unitTests' >> ${RESULTS_DIR}/unittest.txt
    ALL_OK=false
    UNIT_TESTS_OK=false
    $CMS_BOT_DIR/report-pull-request-results PARSE_UNIT_TESTS_FAIL -f $WORKSPACE/unitTests/log.txt --report-file ${RESULTS_DIR}/11-report.res ${REPORT_OPTS}
    echo "UnitTests" > ${RESULTS_DIR}/11-failed.res
  else
    echo 'UNIT_TEST_RESULTS;OK,Unit Tests,See Log,unitTests' >> ${RESULTS_DIR}/unittest.txt
  fi
  echo "<html><head></head><body>" > $WORKSPACE/unitTests/success.html
  cp $WORKSPACE/unitTests/success.html $WORKSPACE/unitTests/failed.html
  UT_ERR=false
  utlog="testing.log"
  for t in $(find $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/src -name ${utlog} -type f | sed "s|$WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/||;s|/${utlog}$||") ; do
    mkdir -p $WORKSPACE/unitTests/${t}
    mv $WORKSPACE/$CMSSW_IB/tmp/${SCRAM_ARCH}/${t}/${utlog} $WORKSPACE/unitTests/${t}/
    if [ $(grep '^\-\-\-> test  *[^ ]*  *succeeded$' $WORKSPACE/unitTests/${t}/${utlog} | wc -l) -gt 0 ] ; then
      echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/unitTests/success.html
    else
      echo "<a href='${t}/${utlog}'>${t}</a><br/>" >> $WORKSPACE/unitTests/failed.html
      UT_ERR=true
    fi
  done
  if ! $UT_ERR ; then echo "No unit test failed" >> $WORKSPACE/unitTests/failed.html ; fi
  echo "</body></html>" >> $WORKSPACE/unitTests/success.html
  echo "</body></html>" >> $WORKSPACE/unitTests/failed.html
  prepare_upload_results
  if $UNIT_TESTS_OK ; then
    mark_commit_status_all_prs 'unittest' 'success' -u "${PR_RESULT_URL}/unitTests" -d "Passed"
  else
    mark_commit_status_all_prs 'unittest' 'error' -u "${PR_RESULT_URL}/unitTests" -d "Some unit tests were failed."
  fi
fi
