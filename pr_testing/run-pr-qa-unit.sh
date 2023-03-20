#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh
CMSSW_PKG_COUNT=$(ls -d $LOCALRT/src/*/* | wc -l)
cd $CMSSW_BASE
RUN_FULL_UNITTEST=false
if $PRODUCTION_RELEASE ; then RUN_FULL_UNITTEST=true ; fi
#For now force disabl full unit tests
RUN_FULL_UNITTEST=false
which dasgoclient

#Drop RELEASE_TOP/external/SCRAM_ARCH/data if LOCALTOP/external/SCRAM_ARCH/data exists
#to make sure external packages removed files are not picked up from release directory
if $BUILD_EXTERNAL ; then
  if [ "X${CMSSW_RELEASE_BASE}" != "X" ] ; then
    export CMSSW_SEARCH_PATH=$(echo $CMSSW_SEARCH_PATH | tr ':' '\n'  | grep -v "$CMSSW_RELEASE_BASE/external/" | tr '\n' ':')
  fi
fi


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
          touch ${WORKSPACE}/update-das-queries
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
  let UT_TIMEOUT=7200+${CMSSW_PKG_COUNT}*20
  UTESTS_CMD="timeout ${UT_TIMEOUT} scram b -k -j ${NCPU}  runtests "
  if ${RUN_FULL_UNITTEST} ; then
    set +x
    curl -k -L -s -o src.tar.gz https://github.com/cms-sw/cmssw/archive/${CMSSW_IB}.tar.gz
    tar -xzf src.tar.gz
    mv cmssw-${CMSSW_IB} fullsrc
    mv fullsrc/Geometry/TrackerSimData/data fullsrc/Geometry/TrackerSimData/data.backup
    for p in $(ls -d fullsrc/*/* | sed 's|fullsrc/||') ; do
      if [ -e $CMSSW_BASE/src/$p ] || [ -e $CMSSW_BASE/poison/$p ] ; then
        echo "Skipped $p"
        continue
      fi
      s=$(echo $p | sed 's|/.*||')
      mkdir -p $CMSSW_BASE/src/$s
      mv fullsrc/$p $CMSSW_BASE/src/$p
      echo "Created $p"
    done
    rm -rf fullsrc src.tar.gz
    scram b -r echo_CXX
    TEST_PATH="${CMSSW_RELEASE_BASE}/test/${SCRAM_ARCH}"
    rpath=$(scram tool info cmssw 2>&1 | grep CMSSW_BASE | sed 's|^CMSSW_BASE=||')
    if [ "${rpath}" != "" ] ; then TEST_PATH="${TEST_PATH}:${rpath}/test/${SCRAM_ARCH}"; fi
    UTESTS_CMD="PATH=${TEST_PATH}:${PATH} timeout 10800 scram b -k -j ${NCPU} unittests "
    set -x
  fi
  echo "LD_LIBRARY_PATH: ${LD_LIBRARY_PATH}"
  scram build echo_LD_LIBRARY_PATH || true
  cms_major=$(echo ${CMSSW_IB} | cut -d_ -f2)
  cms_minor=$(echo ${CMSSW_IB} | cut -d_ -f3)
  cms_ver="$(echo 00${cms_major} | sed -E 's|^.*(..)$|\1|')$(echo 00${cms_minor} | sed -E 's|^.*(..)$|\1|')"
  if [ $cms_ver -ge 1301 ] ; then
    find $CMSSW_BASE/src -type d | grep -v '/__pycache__/*' | xargs chmod -w
    mkdir $CMSSW_BASE/unit_tests
    chmod -w $CMSSW_BASE
  fi
  echo $UTESTS_CMD > $WORKSPACE/unitTests/log.txt
  (eval $UTESTS_CMD && echo 'ALL_OK') > $WORKSPACE/unitTests/log.txt 2>&1 || true
  echo 'END OF UNIT TESTS'
  echo '--------------------------------------'
  if [ $cms_ver -ge 1301 ] ; then
    find $CMSSW_BASE/src -type d | xargs chmod +w
    chmod +w $CMSSW_BASE
  fi
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

  TEST_ERRORS=$(grep -ai 'had errors\|recipe for target' $WORKSPACE/unitTests/log.txt | sed "s|'||g;s|.*recipe for target *||;s|.*unittests_|---> test |;s| failed$| timeout|" || true)
  TEST_ERRORS=`grep -ai "had errors" $WORKSPACE/unitTests/log.txt` || true
  GENERAL_ERRORS=`grep -a "ALL_OK" $WORKSPACE/unitTests/log.txt` || true

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
    if [ $(grep -a '^\-\-\-> test  *[^ ]*  *succeeded$' $WORKSPACE/unitTests/${t}/${utlog} | wc -l) -gt 0 ] ; then
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
    mark_commit_status_all_prs 'unittest' 'success' -u "${BUILD_URL}" -d "Passed"
  else
    mark_commit_status_all_prs 'unittest' 'error' -u "${BUILD_URL}" -d "Some unit tests were failed."
  fi
fi
