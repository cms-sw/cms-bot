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

    BASELINE_DIR=$WORKSPACE/baseline-hlt-p2-timing
    PR_DIR=$WORKSPACE/rundir
    if grep -q "passed" $BASELINE_DIR/status.txt; then
        BASELINE_ARGS_GPU_HLT="$BASELINE_DIR/gpu_memory_ph2_hlt.csv --label1 ${COMPARISON_RELEASE}"
        BASELINE_ARGS_GPU_NGT="$BASELINE_DIR/gpu_memory_ph2_ngt.csv --label1 ${COMPARISON_RELEASE}"
        BASELINE_ARGS_CPU_HLT="$BASELINE_DIR/cpu_memory_ph2_hlt.csv --label1 ${COMPARISON_RELEASE}"
        BASELINE_ARGS_CPU_NGT="$BASELINE_DIR/cpu_memory_ph2_ngt.csv --label1 ${COMPARISON_RELEASE}"
        BASELINE_ARGS_CPU_HLTONCPU="$BASELINE_DIR/cpu_memory_ph2_hlt_onCPU.csv --label1 ${COMPARISON_RELEASE}"
    else
        echo "Baseline job didn't pass, plotting current job only"
        BASELINE_ARGS_GPU_HLT=""
        BASELINE_ARGS_GPU_NGT=""
        BASELINE_ARGS_CPU_HLT=""
        BASELINE_ARGS_CPU_NGT=""
        BASELINE_ARGS_CPU_HLTONCPU=""
    fi

    # run the GPU comparison job for the HLT timing menu
    compareMemoryProfiles.py $PR_DIR/logs.Phase2_L1P2GT_HLT/gpu_memory.csv $BASELINE_ARGS_GPU_HLT \
			     --label2 "${PULL_REQUEST}" --cms-label "cmssw integration" \
			     --no-show --gpu --output hlt_memory_comparison || ERR=1
    # run the GPU comparison job for the NGT menu
    compareMemoryProfiles.py $PR_DIR/logs.NGTScouting_L1P2GT_HLT/gpu_memory.csv $BASELINE_ARGS_GPU_NGT \
			     --label2 "${PULL_REQUEST}" --cms-label "cmssw integration" \
			     --no-show --gpu --output ngt_memory_comparison || ERR=1
    # run the CPU comparison job for the HLT timing menu
    compareMemoryProfiles.py $PR_DIR/logs.Phase2_L1P2GT_HLT/cpu_memory.csv $BASELINE_ARGS_CPU_HLT \
			     --label2 "${PULL_REQUEST}" --cms-label "cmssw integration" \
			     --no-show --output hlt_memory_comparison || ERR=1
    # run the CPU comparison job for the NGT menu
    compareMemoryProfiles.py $PR_DIR/logs.NGTScouting_L1P2GT_HLT/cpu_memory.csv $BASELINE_ARGS_CPU_NGT \
			     --label2 "${PULL_REQUEST}" --cms-label "cmssw integration" \
			     --no-show --output ngt_memory_comparison || ERR=1
    # run the CPU comparison job for the HLT timing menu (on CPU)
    compareMemoryProfiles.py $PR_DIR/logs.Phase2_L1P2GT_HLT_OnCPU/cpu_memory.csv $BASELINE_ARGS_CPU_HLTONCPU \
			     --label2 "${PULL_REQUEST}" --cms-label "cmssw integration" \
			     --no-show --output hltOnCPU_memory_comparison || ERR=1
    
    # copy back the png figures to the output folder
    cp gpu_hlt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
    cp gpu_ngt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
    cp cpu_hlt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
    cp cpu_ngt_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
    cp cpu_hltOnCPU_memory_comparison.png $JENKINS_UPLOAD_DIR/hlt-p2-timing/ || ERR=1
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
      echo "HLT_P2_TIMING_CSV;OK,HLT Phase 2 hardware usage,See summary,hlt-p2-timing" >> ${RESULTS_DIR}/hlt-p2-timing.txt
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

# Generate summary index.html
BUILD_TIMESTAMP=$(date -u '+%Y-%m-%d %H:%M UTC')

# Decide per-menu status based on presence of required output files
HLT_STATUS="&#10003; ok";       HLT_STATUS_CLASS="ok"
HLT_ONCPU_STATUS="&#10003; ok"; HLT_ONCPU_STATUS_CLASS="ok"
NGT_STATUS="&#10003; ok";       NGT_STATUS_CLASS="ok"
[ ! -f "$WORKSPACE/json_upload/Phase2Timing_resources.json" ]       && HLT_STATUS="&#10007; missing"       && HLT_STATUS_CLASS="err"
[ ! -f "$WORKSPACE/json_upload/Phase2Timing_resources_OnCPU.json" ] && HLT_ONCPU_STATUS="&#10007; missing" && HLT_ONCPU_STATUS_CLASS="err"
[ ! -f "$WORKSPACE/json_upload/Phase2Timing_resources_NGT.json" ]   && NGT_STATUS="&#10007; missing"       && NGT_STATUS_CLASS="err"

# Build optional CSV section for CMSSW >= 17
CSV_SECTION=""
if [ "$CMSSW_VERSION_NUMBER" -ge 1700 ]; then
  CSV_SECTION='<div class="section"><div class="section-title">Hardware usage CSVs</div><div class="links">
    <a href="cpu_memory_ph2_hlt.csv">cpu_memory_ph2_hlt.csv</a>
    <a href="gpu_memory_ph2_hlt.csv">gpu_memory_ph2_hlt.csv</a>
    <a href="gpu_usage_ph2_hlt.csv">gpu_usage_ph2_hlt.csv</a>
    <a href="cpu_memory_ph2_hlt_onCPU.csv">cpu_memory_ph2_hlt_onCPU.csv</a>
    <a href="cpu_memory_ph2_ngt.csv">cpu_memory_ph2_ngt.csv</a>
    <a href="gpu_memory_ph2_ngt.csv">gpu_memory_ph2_ngt.csv</a>
    <a href="gpu_usage_ph2_ngt.csv">gpu_usage_ph2_ngt.csv</a>
  </div></div>'
fi

cat > $JENKINS_UPLOAD_DIR/hlt-p2-timing/index.html << EOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HLT Phase-2 Timing &mdash; ${CMSSW_VERSION} #${BUILD_NUMBER}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#f5f5f5;color:#222;padding:2rem;max-width:1100px;margin:0 auto}
h1{font-size:1.4rem;font-weight:500;margin-bottom:.25rem}
.meta{font-size:.85rem;color:#666;margin-bottom:2rem}
.status-bar{display:flex;gap:2rem;background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:1rem 1.5rem;margin-bottom:2rem;flex-wrap:wrap}
.stat{display:flex;flex-direction:column;gap:2px}
.stat-label{font-size:.75rem;color:#888}
.stat-value{font-size:1rem;font-weight:500}
.ok{color:#2a7a2a}.err{color:#c0392b}
.section{margin-bottom:2.5rem}
.section-title{font-size:1rem;font-weight:500;color:#444;margin-bottom:1rem;padding-bottom:.5rem;border-bottom:1px solid #ddd}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}
.card{background:#fff;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden}
.card a{display:block;text-decoration:none;color:inherit}
.card img{width:100%;display:block;background:#eee;transition:opacity .2s}
.card:hover img{opacity:.88}
.placeholder{width:100%;height:140px;background:#f0f0f0;display:flex;align-items:center;justify-content:center;font-size:.8rem;color:#aaa}
.card-body{padding:.75rem 1rem}
.card-title{font-size:.9rem;font-weight:500;margin-bottom:.25rem}
.card-sub{font-size:.8rem;color:#888}
.badge{display:inline-block;font-size:.7rem;padding:2px 7px;border-radius:4px;margin-left:.5rem;font-weight:500;vertical-align:middle}
.badge-gpu{background:#e8eeff;color:#2a47b0}
.badge-cpu{background:#eaf5ea;color:#2a7a2a}
.links{display:flex;flex-direction:column;gap:.5rem;font-size:.9rem}
.links a{color:#1a56db;text-decoration:none}
.links a:hover{text-decoration:underline}
</style>
</head>
<body>
<h1>HLT Phase-2 Timing &mdash; Summary</h1>
<p class="meta">Build <strong>${BUILD_NUMBER}</strong> &nbsp;&middot;&nbsp; <strong>${CMSSW_VERSION}</strong> &nbsp;&middot;&nbsp; Architecture: <strong>${ARCHITECTURE}</strong> &nbsp;&middot;&nbsp; ${BUILD_TIMESTAMP}</p>
<div class="status-bar">
  <div class="stat"><span class="stat-label">Overall</span><span class="stat-value ${ERR:+err}${ERR:-ok}">$([ $ERR -eq 0 ] && echo '&#10003; passed' || echo '&#10007; failed')</span></div>
  <div class="stat"><span class="stat-label">HLT menu</span><span class="stat-value ${HLT_STATUS_CLASS}">${HLT_STATUS}</span></div>
  <div class="stat"><span class="stat-label">HLT on CPU</span><span class="stat-value ${HLT_ONCPU_STATUS_CLASS}">${HLT_ONCPU_STATUS}</span></div>
  <div class="stat"><span class="stat-label">NGT Scouting</span><span class="stat-value ${NGT_STATUS_CLASS}">${NGT_STATUS}</span></div>
  <div class="stat"><span class="stat-label">Baseline</span><span class="stat-value">${COMPARISON_RELEASE}</span></div>
</div>
<div class="section">
  <div class="section-title">Memory comparisons &mdash; HLT Phase-2 menu</div>
  <div class="grid">
    <div class="card"><a href="gpu_hlt_memory_comparison.png"><img src="gpu_hlt_memory_comparison.png" alt="GPU memory - HLT menu" onerror="this.outerHTML='<div class=\'placeholder\'>gpu_hlt_memory_comparison.png not found</div>'"></a><div class="card-body"><div class="card-title">GPU memory <span class="badge badge-gpu">GPU</span></div><div class="card-sub">Phase2_L1P2GT_HLT</div></div></div>
    <div class="card"><a href="cpu_hlt_memory_comparison.png"><img src="cpu_hlt_memory_comparison.png" alt="CPU memory - HLT menu" onerror="this.outerHTML='<div class=\'placeholder\'>cpu_hlt_memory_comparison.png not found</div>'"></a><div class="card-body"><div class="card-title">CPU memory <span class="badge badge-cpu">CPU</span></div><div class="card-sub">Phase2_L1P2GT_HLT</div></div></div>
    <div class="card"><a href="cpu_hltOnCPU_memory_comparison.png"><img src="cpu_hltOnCPU_memory_comparison.png" alt="CPU memory - HLT on CPU" onerror="this.outerHTML='<div class=\'placeholder\'>cpu_hltOnCPU_memory_comparison.png not found</div>'"></a><div class="card-body"><div class="card-title">CPU memory (on CPU run) <span class="badge badge-cpu">CPU</span></div><div class="card-sub">Phase2_L1P2GT_HLT_OnCPU</div></div></div>
  </div>
</div>
<div class="section">
  <div class="section-title">Memory comparisons &mdash; NGT Scouting menu</div>
  <div class="grid">
    <div class="card"><a href="gpu_ngt_memory_comparison.png"><img src="gpu_ngt_memory_comparison.png" alt="GPU memory - NGT Scouting" onerror="this.outerHTML='<div class=\'placeholder\'>gpu_ngt_memory_comparison.png not found</div>'"></a><div class="card-body"><div class="card-title">GPU memory <span class="badge badge-gpu">GPU</span></div><div class="card-sub">NGTScouting_L1P2GT_HLT</div></div></div>
    <div class="card"><a href="cpu_ngt_memory_comparison.png"><img src="cpu_ngt_memory_comparison.png" alt="CPU memory - NGT Scouting" onerror="this.outerHTML='<div class=\'placeholder\'>cpu_ngt_memory_comparison.png not found</div>'"></a><div class="card-body"><div class="card-title">CPU memory <span class="badge badge-cpu">CPU</span></div><div class="card-sub">NGTScouting_L1P2GT_HLT</div></div></div>
  </div>
</div>
${CSV_SECTION}
<div class="section">
  <div class="section-title">Links</div>
  <div class="links">
    <a href="${CHART_URL}">&#9651; Pie chart &mdash; HLT Phase-2 timing (time_thread)</a>
    <a href="../hlt-p2-timing.log">&#128196; Full timing log</a>
    <a href="${BUILD_URL}">&#128296; Jenkins build</a>
  </div>
</div>
</body>
</html>
EOF

rm -rf $WORKSPACE/json_upload $WORKSPACE/rundir
prepare_upload_results
