#!/bin/sh -ex
TEST_FLAVOR=$1
CMS_BOT_DIR=$(dirname $(realpath $0))
REL_BASELINE_DIR="ib-baseline-tests/${RELEASE_FORMAT}/${ARCHITECTURE}/${REAL_ARCH}/new-matrix${TEST_FLAVOR}-results"
source $CMS_BOT_DIR/jenkins-artifacts
#Run on any machine to see which workflows should be run
if ! $FORCE_RUN ; then
  echo "${WORKFLOWS}" > ${WORKSPACE}/workflows-${BUILD_ID}.log
  send_jenkins_artifacts ${WORKSPACE}/workflows-${BUILD_ID}.log ${REL_BASELINE_DIR}/workflows-${BUILD_ID}.log
  OPTS=""
  case "${TEST_FLAVOR}" in
    gpu ) OPTS="-w gpu" ;;
    high_stats ) ;;
    * ) ;;
  esac
  runTheMatrix.py -n ${OPTS} ${MATRIX_ARGS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' > $WORKSPACE/all.wfs
  echo "Total WFs: $(cat $WORKSPACE/all.wfs |wc -l)"
  REL_WFS=""
  if has_jenkins_artifacts ${REL_BASELINE_DIR} -d ; then
    REL_WFS=$(cmd_jenkins_artifacts ${REL_BASELINE_DIR} "cat runall-report-step123*.log 2>/dev/null" | grep '_' | sed 's|_.*||' | tr '\n' ' ')
  fi
  runTheMatrix.py -n ${OPTS} ${MATRIX_ARGS} ${WORKFLOWS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' > $WORKSPACE/req.wfs
  for wf in $(cat $WORKSPACE/req.wfs) ; do
    [ $(grep "^${wf}$" $WORKSPACE/all.wfs | wc -l) -gt 0 ] || continue
    [ $(echo " $REL_WFS " | grep " $wf "  | wc -l) -eq 0 ] || continue
    WFS="${wf},${WFS}"
  done
  WFS=$(echo ${WFS} | sed 's|,$||')
  [ "${WFS}" = "" ] && exit 0
  echo "MATRIX_ARGS=${MATRIX_ARGS} -l ${WFS}" > $WORKSPACE/rerun.txt
  echo "FORCE_RUN=true"                      >> $WORKSPACE/rerun.txt
  exit 0
fi

#Actually run  runTheMatrix.py for the selected workflows
mkdir -p "$WORKSPACE/matrix-results"
pushd "$WORKSPACE/matrix-results"
  CMD_OPTS=""
  case "${TEST_FLAVOR}" in
    gpu )        MATRIX_ARGS="-w gpu ${MATRIX_ARGS}" ;;
    high_stats ) CMD_OPTS="-n 1000" ;;
    * ) ;;
  esac
  [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && MATRIX_ARGS="--job-reports $MATRIX_ARGS"
  [ -f ${CMSSW_RELEASE_BASE}/src/Validation/Performance/python/TimeMemoryJobReport.py ] && CMD_OPTS="${CMD_OPTS} --customise Validation/Performance/TimeMemoryJobReport.customiseWithTimeMemoryJobReport"
  [ "${CMD_OPTS}" != "" ] && MATRIX_ARGS="${MATRIX_ARGS} --command ' ${CMD_OPTS}'"
  eval CMS_PATH=/cvmfs/cms-ib.cern.ch runTheMatrix.py -j $(nproc) ${MATRIX_ARGS} 2>&1 | tee -a matrixTests.${BUILD_ID}.log
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
