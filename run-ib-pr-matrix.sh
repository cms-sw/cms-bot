#!/bin/bash -ex
TEST_FLAVOR=$1
CMS_BOT_DIR=$(cd $(dirname $0) >/dev/null 2>&1; pwd -P)
readarray -t ALL_GPU_TYPES < ${CMS_BOT_DIR}/gpu_flavors.txt
ARTIFACT_DIR="ib-baseline-tests/${RELEASE_FORMAT}/${ARCHITECTURE}/${REAL_ARCH}/matrix${TEST_FLAVOR}-results"
source $CMS_BOT_DIR/jenkins-artifacts
source $CMS_BOT_DIR/pr_testing/_helper_functions.sh
#Run on any machine to see which workflows should be run
if [ "${CHECK_WORKFLOWS}" = "true" ] ; then
  echo "${WORKFLOWS}" > ${WORKSPACE}/workflows-${BUILD_ID}.log
  send_jenkins_artifacts ${WORKSPACE}/workflows-${BUILD_ID}.log ${ARTIFACT_DIR}/workflows-${BUILD_ID}.log
  OPTS=""
  case "${TEST_FLAVOR}" in
    high_stats ) ;;
    nano ) OPTS="-w nano" ;;
    * ) if is_in_array "${TEST_FLAVOR}" "${ALL_GPU_TYPES[@]}" ; then
          OPTS=$(get_gpu_matrix_args | sed -r 's|--gpu  *[a-z_-]+||')
        fi
        ;;
  esac
  REL_WFS=""
  if has_jenkins_artifacts ${ARTIFACT_DIR} -d ; then
    REL_WFS=$(cmd_jenkins_artifacts ${ARTIFACT_DIR} "cat runall-report-step123*.log 2>/dev/null" | grep '_' | sed 's|_.*||' | tr '\n' ' ')
  fi
  if [ $(echo "${WORKFLOWS}" | sed 's|.*-l ||;s| .*||' | tr ',' '\n' | grep '^all$' | wc -l) -gt 0 ] ; then
    ALL_WFS=$(runTheMatrix.py -n ${OPTS} ${MATRIX_ARGS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' | tr '\n' ',' | sed 's|,$||')
    WORKFLOWS=$(echo "${WORKFLOWS}" | sed "s|all|${ALL_WFS}|")
  fi
  rm -f $WORKSPACE/req.wfs
  if  ! check_invalid_wf_lists "${WORKFLOWS}" false ; then
    touch $WORKSPACE/req.wfs
  else
    runTheMatrix.py -n ${OPTS} ${MATRIX_ARGS} ${WORKFLOWS} | grep -v ' workflows ' | grep '^[1-9][0-9]*\(.[0-9][0-9]*\|\)\s' | sed 's| .*||' > $WORKSPACE/req.wfs
  fi
  for wf in $(cat $WORKSPACE/req.wfs) ; do
      [ $(echo " $REL_WFS " | grep " $wf "  | wc -l) -eq 0 ] || continue
      WFS="${wf},${WFS}"
  done
  WFS=$(echo ${WFS} | sed 's|,$||')

  if [ "${WFS}" = "" ] ; then
    mv ${WORKSPACE}/workflows-${BUILD_ID}.log ${WORKSPACE}/workflows-${BUILD_ID}.done
    send_jenkins_artifacts ${WORKSPACE}/workflows-${BUILD_ID}.done ${ARTIFACT_DIR}/workflows-${BUILD_ID}.done
    echo "ARTIFACT_DIR=${ARTIFACT_DIR}" > $WORKSPACE/cvmfs-deploy-baseline
    echo "CVMFS_SERVER=cms-ci"         >> $WORKSPACE/cvmfs-deploy-baseline
    exit 0
  fi
  echo "CHECK_WORKFLOWS=false"                 > ${WORKSPACE}/rerun.txt
  echo "MATRIX_ARGS=${MATRIX_ARGS} -l ${WFS}" >> ${WORKSPACE}/rerun.txt
  exit 0
fi

#Actually run  runTheMatrix.py for the selected workflows
mkdir -p "$WORKSPACE/matrix-results"
UC_TEST_FLAVOR=$(echo ${TEST_FLAVOR} | tr '[a-z]' '[A-Z]')
[ "${PRODUCTION_RELEASE}" != "true" ] && PRODUCTION_RELEASE="false"
pushd "$WORKSPACE/matrix-results"
  NJOBS=$(nproc)
  CMD_OPTS=""
  if ${PRODUCTION_RELEASE} && cmsDriver.py --help | grep -q '\-\-maxmem_profile'  ; then
    if [ "${TEST_FLAVOR}" != "rocm" ]; then
      CMD_OPTS="--maxmem_profile"
    fi
  fi
  case "${TEST_FLAVOR}" in
    high_stats ) CMD_OPTS="-n 500" ; MATRIX_ARGS="-i all ${MATRIX_ARGS}" ;;
    threading )  MATRIX_ARGS="-i all -t 4 ${MATRIX_ARGS}" ; let NJOBS=(${NJOBS}/4)+1 ;;
    nano )       MATRIX_ARGS="-w nano -i all ${MATRIX_ARGS}" ;;
    input )      MATRIX_ARGS="-i all --maxSteps=2 ${MATRIX_ARGS}" ; CMD_OPTS="-n 1 --prefix ${CMS_BOT_DIR}/pr_testing/retry-command.sh" ; export CMS_BOT_RETRY_COUNT=3 ;;
    * ) if is_in_array "${TEST_FLAVOR}" "${ALL_GPU_TYPES[@]}" ; then
          MATRIX_ARGS="$(get_gpu_matrix_args) ${MATRIX_ARGS}"
        fi
        ;;
  esac
  [ $(runTheMatrix.py --help | grep 'job-reports' | wc -l) -gt 0 ] && MATRIX_ARGS="--job-reports $MATRIX_ARGS"
  [ -f ${CMSSW_RELEASE_BASE}/src/Validation/Performance/python/TimeMemoryJobReport.py ] && CMD_OPTS="${CMD_OPTS} --customise Validation/Performance/TimeMemoryJobReport.customiseWithTimeMemoryJobReport"
  if [ "${TEST_FLAVOR}" != "" ] ; then
    eval "a=\${EXTRA_MATRIX_COMMAND_ARGS_${UC_TEST_FLAVOR}}"
    CMD_OPTS="${CMD_OPTS} ${a}"
  else
    CMD_OPTS="${CMD_OPTS} ${EXTRA_MATRIX_COMMAND_ARGS}"
  fi
  [ "${CMD_OPTS}" != "" ] && MATRIX_ARGS="${MATRIX_ARGS} --command ' ${CMD_OPTS}'"
  if [ "X$CMS_SITE_OVERRIDE" == "X" ]; then
    CMS_SITE_OVERRIDE="local"
  fi

  # Check what workflows will be ran
  if ! check_invalid_wf_lists "${MATRIX_ARGS}" ; then
    exit 1
  fi

  eval CMS_PATH=/cvmfs/cms-ib.cern.ch SITECONFIG_PATH=/cvmfs/cms-ib.cern.ch/SITECONF/$CMS_SITE_OVERRIDE runTheMatrix.py -j ${NJOBS} ${MATRIX_ARGS} 2>&1 | tee -a matrixTests.${BUILD_ID}.log
  mv runall-report-step123-.log runall-report-step123-.${BUILD_ID}.log
  find . -name DQM*.root | sort | sed 's|^./||' > wf_mapping.${BUILD_ID}.txt
  ERRORS_FILE=wf_errors.${BUILD_ID}.txt
  touch $ERRORS_FILE
  set +x
  grep "ERROR executing.*" matrixTests.${BUILD_ID}.log | while read line ; do
    WF_STEP=$(echo "$line" | sed 's/.* cd //g' | sed 's/_.*step/;/g' | sed 's/_.*$//g')
    if ! grep $WF_STEP $ERRORS_FILE; then
      echo $WF_STEP >> $ERRORS_FILE
    fi
  done
  set -x

  if [[ $CMD_OPTS =~ maxmem_profile ]] ; then
    LOG=runall-report-step123-.${BUILD_ID}.log
    for WF in $(grep -a '^[1-9][0-9]*' ${LOG} | grep ' Step[0-9]' | sed 's| .*||' | sort | uniq ) ; do
      memFile=maxmem_profile_$(echo $WF | cut -d_ -f1).txt
      pushd $WF
      for log in $(ls step*.log);do
        echo ${log} | cut -d_ -f1 >> ${memFile}
        grep "Memory Report: " $log | tail -5 >> ${memFile}
      done
      popd
    done
  fi 

popd

if [ "${UPLOAD_ARTIFACTS}" = "true" ] ; then
  [ -f ${LOCALRT}/used-ibeos-sort ] && mv ${LOCALRT}/used-ibeos-sort $WORKSPACE/matrix-results/
  echo "${WORKFLOWS}" > ${WORKSPACE}/matrix-results/workflows-${BUILD_ID}.done
  set +x
  NUM_PROC=$(nproc)
  for r in $(find ${WORKSPACE}/matrix-results -name 'step*.root' -type f | grep -v 'inDQM.root$') ; do
    while [ $(jobs -p | wc -l) -gt ${NUM_PROC} ] ; do sleep 0.1 ; done
    echo "Running edmEventSize and edmProvDump: $r"
    (edmEventSize -v $r > $r.edmEventSize || true) &
    (edmProvDump     $r > $r.edmProvDump  || true) &
  done
  set -x
  jobs
  wait
  send_jenkins_artifacts $WORKSPACE/matrix-results/ ${ARTIFACT_DIR}
  echo "ARTIFACT_DIR=${ARTIFACT_DIR}" > $WORKSPACE/cvmfs-deploy-baseline
  echo "CVMFS_SERVER=cms-ci"         >> $WORKSPACE/cvmfs-deploy-baseline

  REL_QUEUE=$(echo ${RELEASE_FORMAT} | sed 's|_X_.*|_X|')
  if python3 -V ; then
    DEV_QUEUE=$(cd ${CMS_BOT_DIR}; python3 -c 'from releases import CMSSW_DEVEL_BRANCH; print (CMSSW_DEVEL_BRANCH)')
  else
    DEV_QUEUE=$(cd ${CMS_BOT_DIR}; python -c 'from releases import CMSSW_DEVEL_BRANCH; print (CMSSW_DEVEL_BRANCH)')
  fi
  if [ "X${REL_QUEUE}" = "X${DEV_QUEUE}" ] ; then
    echo "${REL_QUEUE}" > $WORKSPACE/BaselineDevRelease
    send_jenkins_artifacts $WORKSPACE/BaselineDevRelease ib-baseline-tests/BaselineDevRelease
  fi
fi
