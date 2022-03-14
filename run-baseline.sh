#!/bin/sh -ex
TEST_FLAVOR=$1
CMS_BOT_DIR=$(dirname $(realpath $0))
function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(nproc)
  if [ "X$1" != "X" ] ; then
    let ACTUAL_CPU=$ACTUAL_CPU*$1 || true
  fi
  echo $ACTUAL_CPU
}
REL_BASELINE_DIR="ib-baseline-tests/${RELEASE_FORMAT}/${ARCHITECTURE}/${REAL_ARCH}/new-matrix${TEST_FLAVOR}-results"
mkdir -p "$WORKSPACE/matrix-results"
pushd "$WORKSPACE/matrix-results"
  source $CMS_BOT_DIR/jenkins-artifacts
  MATRIX_OPTS="-j $(Jenkins_GetCPU) ${MATRIX_ARGS}"
  case "${TEST_FLAVOR}" in
    gpu ) MATRIX_OPTS="${MATRIX_OPTS} -w gpu" ;;
    high_stats ) ;;
    * ) ;;
  esac
  runTheMatrix.py -n ${MATRIX_OPTS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' > $WORKSPACE/all.wfs
  echo "Total WFs: $(cat $WORKSPACE/all.wfs |wc -l)"
  REL_WFS=$(cmd_jenkins_artifacts ${REL_BASELINE_DIR} "cat runall-report-step123*.log 2>/dev/null" | grep '_' | sed 's|_.*||' | tr '\n' ' ')
  runTheMatrix.py -n ${MATRIX_OPTS} ${WORKFLOWS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' > $WORKSPACE/req.wfs
  for wf in $(cat $WORKSPACE/req.wfs) ; do
    [ $(grep "^${wf}$" $WORKSPACE/all.wfs | wc -l) -gt 0 ] || continue
    [ $(echo " $REL_WFS " | grep " $wf "  | wc -l) -eq 0 ] || continue
    WFS="${wf},${WFS}"    
  done
  WFS=$(echo ${WFS} | sed 's|,$||')
  [ "${WFS}" = "" ] && exit 0
  MATRIX_OPTS="${MATRIX_OPTS} -l ${WFS}"
  [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && MATRIX_OPTS="--job-reports $MATRIX_OPTS"
  if [ -f ${CMSSW_RELEASE_BASE}/src/Validation/Performance/python/TimeMemoryJobReport.py ]; then 
    [ $(runTheMatrix.py --help | grep 'command' | wc -l) -gt 0 ] && MATRIX_OPTS="--command ' --customise Validation/Performance/TimeMemoryJobReport.customiseWithTimeMemoryJobReport' $MATRIX_OPTS"
  fi
  eval CMS_PATH=/cvmfs/cms-ib.cern.ch runTheMatrix.py ${MATRIX_OPTS} 2>&1 | tee -a matrixTests.${BUILD_ID}.log
  mv runall-report-step123-.log runall-report-step123-.${BUILD_ID}.log
  MAPPING_FILE=wf_mapping.${BUILD_ID}.txt
  for f in $(find . -name DQM*.root | sort) ; do
    WF_PATH=`echo $f | sed 's/^\.\///'`
    WF_NUMBER=`echo $WF_PATH | sed 's/_.*$//'`
    echo $WF_PATH >> $MAPPING_FILE
  done
  ERRORS_FILE=wf_errors.${BUILD_ID}.txt
  touch $ERRORS_FILE
  grep "ERROR executing.*" matrixTests.${BUILD_ID}.log | while read line ; do
    WF_STEP=$(echo "$line" | sed 's/.* cd //g' | sed 's/_.*step/;/g' | sed 's/_.*$//g')
    if ! grep $WF_STEP $ERRORS_FILE; then
      echo $WF_STEP >> $ERRORS_FILE
    fi
  done
popd

send_jenkins_artifacts $WORKSPACE/matrix-results/ ${REL_BASELINE_DIR}
