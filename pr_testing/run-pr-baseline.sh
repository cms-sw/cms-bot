#!/bin/sh -ex
TEST_FLAVOR=$1
CMS_BOT_DIR=$(dirname $0)
case $CMS_BOT_DIR in /*) ;; *) CMS_BOT_DIR=$(pwd)/${CMS_BOT_DIR} ;; esac
CMS_BOT_DIR=$(dirname ${CMS_BOT_DIR})
function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(nproc)
  if [ "X$1" != "X" ] ; then
    let ACTUAL_CPU=$ACTUAL_CPU*$1 || true
  fi
  echo $ACTUAL_CPU
}
REL_BASELINE_DIR="ib-baseline-tests/${RELEASE_FORMAT}/${ARCHITECTURE}/${REAL_ARCH}/matrix${TEST_FLAVOR}-results"
mkdir -p "$WORKSPACE/matrix-results"
pushd "$WORKSPACE/matrix-results"
  source $CMS_BOT_DIR/jenkins-artifacts
  MATRIX_OPTS="-j $(Jenkins_GetCPU) ${EXTRA_MATRIX_ARGS}"
  [ "${TEST_FLAVOR}" = "gpu" ] && MATRIX_OPTS="${MATRIX_OPTS} -w gpu"
  runTheMatrix.py -n ${MATRIX_OPTS} | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)  *[^\s]*$' | sed 's| .*||' > $WORKSPACE/all.wfs
  REL_WFS=$(cmd_jenkins_artifacts ${REL_BASELINE_DIR} "cat runall-report-step123*" | grep '_' | sed 's|_.*||' | tr '\n' ' ')
  WFS=""
  for wf in $(echo ${MATRIX_EXTRAS} | tr ',' '\n') ;  do
    [ $(echo " $REL_WFS " | grep " $wf " | wc -l) -eq 0 ] || continue
    [ $(grep "^${wf}$" $WORKSPACE/all.wfs | wc -l) -gt 0 ] || continue
    WFS="${wf},${WFS}"
  done
  WFS=$(echo ${WFS} | sed 's|,$||')
  [ "${WFS}" = "" ] && exit 0
  MATRIX_OPTS="${MATRIX_OPTS} -l ${WFS}"
  [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && MATRIX_OPTS="--job-reports $MATRIX_OPTS"
  if [ -f ${CMSSW_RELEASE_BASE}/src/Validation/Performance/python/TimeMemoryJobReport.py ]; then 
    [ $(runTheMatrix.py --help | grep 'command' | wc -l) -gt 0 ] && MATRIX_OPTS="--command ' --customise Validation/Performance/TimeMemoryJobReport.customiseWithTimeMemoryJobReport' $MATRIX_OPTS"
  fi
  eval CMS_PATH=/cvmfs/cms-ib.cern.ch runTheMatrix.py ${MATRIX_OPTS} 2>&1 | tee -a matrixTests.log.${BUILD_ID}
  mv runall-report-step123-.log runall-report-step123-.log.${BUILD_ID}
  MAPPING_FILE=wf_mapping.txt.${BUILD_ID}
  for f in $(find . -name DQM*.root | sort) ; do
    WF_PATH=`echo $f | sed 's/^\.\///'`
    WF_NUMBER=`echo $WF_PATH | sed 's/_.*$//'`
    echo $WF_PATH >> $MAPPING_FILE
  done
  ERRORS_FILE=wf_errors.txt.${BUILD_ID}
  touch $ERRORS_FILE
  grep "ERROR executing.*" matrixTests.log.${BUILD_ID} | while read line ; do
    WF_STEP=$(echo "$line" | sed 's/.* cd //g' | sed 's/_.*step/;/g' | sed 's/_.*$//g')
    if ! grep $WF_STEP $ERRORS_FILE; then
      echo $WF_STEP >> $ERRORS_FILE
    fi
  done
popd

send_jenkins_artifacts $WORKSPACE/matrix-results/ ${REL_BASELINE_DIR}
echo "RELEASE_FORMAT=${RELEASE_FORMAT}" > $WORKSPACE/cvmfs-deploy-baseline
echo "ARCHITECTURE=${ARCHITECTURE}"    >> $WORKSPACE/cvmfs-deploy-baseline
echo "TEST_FLAVOR=${TEST_FLAVOR}"      >> $WORKSPACE/cvmfs-deploy-baseline
echo "REAL_ARCH=${REAL_ARCH}"          >> $WORKSPACE/cvmfs-deploy-baseline
