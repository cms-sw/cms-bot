#!/bin/bash -ex
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | sed 's|^.*/||;s|#||')
UPLOAD_PATH="${CMSSW_VERSION}-${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Running"

ls -l /eos/cms/store
# Do work
HLT_P2_SCRIPT="src/HLTrigger/Configuration/python/HLT_75e33/test"
HLT_BASEDIR="${CMSSW_BASE}"
if [ ! -e "${HLT_BASEDIR}/${HLT_P2_SCRIPT}" ] ; then HLT_BASEDIR="${CMSSW_RELEASE_BASE}" ; fi
mkdir -p ${RESULTS_DIR} $WORKSPACE/json_upload
cp -r ${HLT_BASEDIR}/${HLT_P2_SCRIPT} $WORKSPACE/rundir
rm -rf $WORKSPACE/rundir/__pycache__

upload_gpu_csvs() {
  mkdir -p $JENKINS_UPLOAD_DIR/hlt-p2-timing

  # HLT timing menu files
  cp $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT/cpu_memory.csv $JENKINS_UPLOAD_DIR/hlt-p2-timing/cpu_memory_ph2_hlt.csv || return 1
  cp $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT/gpu_memory.csv $JENKINS_UPLOAD_DIR/hlt-p2-timing/gpu_memory_ph2_hlt.csv || return 1
  cp $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT/gpu_usage.csv  $JENKINS_UPLOAD_DIR/hlt-p2-timing/gpu_usage_ph2_hlt.csv || return 1

  # HLT timing menu (on CPU) files
  cp $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT_OnCPU/cpu_memory.csv $JENKINS_UPLOAD_DIR/hlt-p2-timing/cpu_memory_ph2_hlt_onCPU.csv || return 1

  # NGT Scouting menu files
  cp $WORKSPACE/rundir/logs.NGTScouting_L1P2GT_HLT/cpu_memory.csv $JENKINS_UPLOAD_DIR/hlt-p2-timing/cpu_memory_ph2_ngt.csv ||  return 1
  cp $WORKSPACE/rundir/logs.NGTScouting_L1P2GT_HLT/gpu_memory.csv $JENKINS_UPLOAD_DIR/hlt-p2-timing/gpu_memory_ph2_ngt.csv || return 1
  cp $WORKSPACE/rundir/logs.NGTScouting_L1P2GT_HLT/gpu_usage.csv  $JENKINS_UPLOAD_DIR/hlt-p2-timing/gpu_usage_ph2_ngt.csv ||  return 1
}

ERR=0
pushd $WORKSPACE/rundir
  export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
  set -o pipefail # required for correct error status piping
  timeout $TIMEOUT bash -e ${HLT_BASEDIR}/${HLT_P2_SCRIPT}/runHLTTiming.sh 2>&1 | tee -a ${WORKSPACE}/hlt-p2-timing.log || ERR=1
  # if the release is greater or equal to CMSSW_17_0_X upload the csv files
  if [ "$CMSSW_VERSION_NUMBER" -ge 1700 ]; then
      if ! upload_gpu_csvs ; then
         echo "ERROR: Failed to copy Generated CSV files" >> ${WORKSPACE}/hlt-p2-timing.log
         echo "ERROR" > $JENKINS_UPLOAD_DIR/hlt-p2-timing/status
		 ERR=1
	  fi
  fi
  set +o pipefail
popd

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts

# check if the comparison script is available and if it is produce comparison plots
if which compareMemoryProfiles.py >/dev/null 2>&1; then

    # create folder for the baseline
    mkdir -p $WORKSPACE/baseline-hlt-p2-timing
    # get the csv files for the baseline
    get_jenkins_artifacts hlt-p2-timing/${COMPARISON_RELEASE}/${COMPARISON_ARCH}/ $WORKSPACE/baseline-hlt-p2-timing/

    # first check if the baseline job succeeded
    if grep -q "passed" $WORKSPACE/baseline-hlt-p2-timing/status.txt; then
	  # run the GPU comparison job for the HLT timing menu
	  compareMemoryProfiles.py $WORKSPACE/baseline-hlt-p2-timing/gpu_memory_ph2_hlt.csv $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT/gpu_memory.csv \
	    --label1 ${COMPARISON_RELEASE} --label2 "${PULL_REQUEST}"  --cms-label "cmssw integration" \
	    --no-show --gpu --output hlt_memory_comparison || ERR=1
	  # run the GPU comparison job for the NGT menu
	  compareMemoryProfiles.py $WORKSPACE/baseline-hlt-p2-timing/gpu_memory_ph2_ngt.csv $WORKSPACE/rundir/logs.NGTScouting_L1P2GT_HLT/gpu_memory.csv \
	    --label1 ${COMPARISON_RELEASE} --label2 "${PULL_REQUEST}"  --cms-label "cmssw integration" \
	    --no-show --gpu --output ngt_memory_comparison  || ERR=1
	  # run the CPU comparison job for the HLT timing menu
	  compareMemoryProfiles.py $WORKSPACE/baseline-hlt-p2-timing/cpu_memory_ph2_hlt.csv $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT/cpu_memory.csv \
	    --label1 ${COMPARISON_RELEASE} --label2 "${PULL_REQUEST}"  --cms-label "cmssw integration" \
	    --no-show --output hlt_memory_comparison || ERR=1
	  # run the CPU comparison job for the NGT menu
	  compareMemoryProfiles.py $WORKSPACE/baseline-hlt-p2-timing/cpu_memory_ph2_ngt.csv $WORKSPACE/rundir/logs.NGTScouting_L1P2GT_HLT/cpu_memory.csv \
	    --label1 ${COMPARISON_RELEASE} --label2 "${PULL_REQUEST}"  --cms-label "cmssw integration" \
	    --no-show --output ngt_memory_comparison  || ERR=1
	  # run the CPU comparison job for the HL timing menu (on CPU)
	  compareMemoryProfiles.py $WORKSPACE/baseline-hlt-p2-timing/cpu_memory_ph2_hlt_onCPU.csv $WORKSPACE/rundir/logs.Phase2_L1P2GT_HLT_OnCPU/cpu_memory.csv \
	    --label1 ${COMPARISON_RELEASE} --label2 "${PULL_REQUEST}"  --cms-label "cmssw integration" \
	    --no-show --output hltOnCPU_memory_comparison  || ERR=1

	  # copy back the png figures on the output folder
	  cp gpu_hlt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
	  cp gpu_ngt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1

	  cp cpu_hlt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
	  cp cpu_ngt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
	  cp cpu_hltOnCPU_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
    else
	  echo "Baseline job didn't pass, not executing any comparison"
    fi
else
    echo "compareMemoryProfiles.py is NOT available"
fi

touch ${RESULTS_DIR}/11-hlt-p2-timing-report.res ${RESULTS_DIR}/11-hlt-p2-timing-failed.res

required_files=(
    "$WORKSPACE/rundir/Phase2Timing_resources.json"
)

if [ "$CMSSW_VERSION_NUMBER" -ge 1501 ]; then
    required_files+=(
        "$WORKSPACE/rundir/Phase2Timing_resources_NGT.json"
    )
fi

if [ "$CMSSW_VERSION_NUMBER" -ge 1600 ]; then
    required_files+=(
        "$WORKSPACE/rundir/Phase2Timing_resources_OnCPU.json"
    )
fi

missing=$ERR
for f in "${required_files[@]}"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: Missing required file: $f" >> ${WORKSPACE}/hlt-p2-timing.log
        missing=1
    fi
done

if [ $missing -eq 0 ]; then
  CHART_URL="https://cmssdt.cern.ch/circles/web/piechart.php?data_name=hlt-p2-timing&resource=time_thread&filter=${CMSSW_VERSION}&dataset=${UPLOAD_PATH}/Phase2Timing_resources"
  echo "HLT_P2_TIMING;SUCCESS,HLT Phase 2 timing Test,See Chart,${CHART_URL}" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo "HLT_P2_TIMING_LOG;OK,HLT Phase 2 timing Test Log,See Logs,hlt-p2-timing.log" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  if [ "$CMSSW_VERSION_NUMBER" -ge 1700 ]; then
      echo "HLT_P2_TIMING_CSV;OK,HLT Phase 2 hardware usage,See Logs,hlt-p2-timing" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  fi
  echo -e "**HLT P2 Timing**: [chart](${CHART_URL})" > ${RESULTS_DIR}/11-hlt-p2-timing-report.res

  mv $WORKSPACE/rundir/Phase2Timing*.json $WORKSPACE/json_upload
  send_jenkins_artifacts $WORKSPACE/json_upload hlt-p2-timing/${UPLOAD_PATH}
  mark_commit_status_all_prs 'hlt-p2-timing' 'success' -u "${BUILD_URL}" -d "HLT Phase2 timing data collected"
else
  echo "HLT_P2_TIMING;ERROR,HLT Phase 2 timing Test,See Logs,hlt-p2-timing.log" >> ${RESULTS_DIR}/hlt-p2-timing.txt
  echo "HLTP2Timing" > ${RESULTS_DIR}/11-hlt-p2-timing-failed.res
  mark_commit_status_all_prs 'hlt-p2-timing' 'error' -u "${BUILD_URL}" -d "HLT Phase2 timing script failed"
fi
rm -rf $WORKSPACE/json_upload $WORKSPACE/rundir
prepare_upload_results
