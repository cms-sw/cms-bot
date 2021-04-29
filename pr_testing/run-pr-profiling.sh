#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

ALLOWED_PROFILING_WORKFLOWS=$(grep "PR_TEST_MATRIX_EXTRAS_PROFILING=" $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||;s|,| |')

for PROFILING_WORKFLOW in $PROFILING_WORKFLOWS;do
  if echo $ALLOWED_PROFILING_WORKFLOWS | grep -qw $PROFLING_WORKFLOW ; then
    WORKFLOWS="$WORKFLOW $PROFILING_WORKFLOW"
  else
    echo "Workflow $PROFILING_WORKFLOW not in allowed workflows $ALLOWED_WORKFLOW_LIST"
  fi
done

git clone --depth 1 https://github.com/cms-cmpwg/profiling.git
mark_commit_status_all_prs 'profiling' 'pending' -u "${BUILD_URL}" -d "Running tests" || true
mkdir -p $WORKSPACE/upload/profiling/
echo "<html><head></head><title>Profiling results</title><body><ul>" > $WORKSPACE/upload/profiling/index.html
LOCALREL=${WORKSPACE}/${CMSSW_VERSION}
export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
for PROFILING_WORKFLOW in $WORKFLOWS;do
  export PROFILING_WORKFLOW
  $WORKSPACE/profiling/Gen_tool/Gen.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_cpu.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_mem.sh $CMSSW_VERSION || true
  pushd $WORKSPACE/$CMSSW_VERSION/$PROFILING_WORKFLOW
  ./profile.sh $CMSSW_VERSION || true
  echo "<li><a href=\"$PROFILING_WORKFLOW/\">$PROFILING_WORKFLOW/</a> </li>" >> $WORKSPACE/upload/profiling/index.html
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/RES_CPU_step3.txt  ${CMSSW_VERSION}_RES_CPU_step3.txt || true
  $WORKSPACE/profiling/Analyze_tool/compare_cpu_txt.py --old ${CMSSW_VERSION}_RES_CPU_step3.txt --new RES_CPU_step3.txt > RES_CPU_compare_$PROFILING_WORKFLOW.txt || true
  echo "<li><a href=\"$PROFILING_WORKFLOW/RES_CPU_compare_$PROFILING_WORKFLOW.txt\">Igprof Comparison cpu usage RECO produce methods.</a> </li>" >> $WORKSPACE/upload/profiling/index.html
  cp $WORKSPACE/cms-bot/comparisons/compareProducts.* ./
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/step3_sizes_${PROFILING_WORKFLOW}.txt  step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt || true
  if [ $(ls -d step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt | wc -l) -gt 0 ]; then
    edmEventSize -v $WORKSPACE/step3*.root > step3_sizes_${PROFILING_WORKFLOW}.txt || true
    ls -l 
    ./compareProducts.sh step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt step3_sizes_${PROFILING_WORKFLOW}.txt _ 100 10 > products_AOD_sizes_compare_${PROFILING_WORKFLOW}.txt || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/products_AOD_sizes_compare_${PROFILING_WORKFLOW}.txt\"> edmEventSize Comparison AOD output.</a> </li>" >> $WORKSPACE/upload/profiling/index.html
  fi
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/step4_sizes_${PROFILING_WORKFLOW}.txt  step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt || true
  if [ $(ls -d step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt | wc -l) -gt 0 ]; then
    edmEventSize -v $WORKSPACE/step4*.root > step4_sizes_${PROFILING_WORKFLOW}.txt || true
    ls -l 
    ./compareProducts.sh step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt step4_sizes_${PROFILING_WORKFLOW}.txt _ 100 10 > products_miniAOD_sizes_compare_${PROFILING_WORKFLOW}.txt || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/products_miniAOD_sizes_compare_${PROFILING_WORKFLOW}.txt\"> edmEventSize Comparison miniAOD output.</a> </li>" >> $WORKSPACE/upload/profiling/index.html
  fi
  popd
  pushd $WORKSPACE/$CMSSW_VERSION || true
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.sql3') ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
    mkdir -p $LOCALREL/igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    BASENAME=$(basename $f)
    ln -s /data/sdt/SDT/jenkins-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}/profiling/$d/$BASENAME $LOCALREL/igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/$BASENAME || true
    ls -l $WORKSPACE/igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/$BASENAME || true
    echo "<li><a href=\"https://cmssdt.cern.ch/SDT/cgi-bin/igprof-navigator/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.sql3/}\"> $(basename $f)</a> </li>" >> $WORKSPACE/upload/profiling/index.html
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.json' ) ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
    mkdir -p $WORKSPACE/upload/profiles/$d || true
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    ln -s /data/sdt/SDT/jenkins-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}/profiling/$d/$BASENAME $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    ls -l $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/$BASENAME || true
    AMP="&"
    echo "<li><a href=\"https://cmssdt.cern.ch/circles/web/piechart.php?local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index.html
  done
  echo "</ul></body></html>" >> $WORKSPACE/upload/profiling/index.html
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.log' -o -name '*.txt') ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
  done
  popd
done
if [ -z ${NO_POST} ] ; then
  if [ -d $LOCALREL/profiling ]; then
    send_jenkins_artifacts $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH} profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/
  fi
  if [ -d $LOCALREL/igprof ]; then
    send_jenkins_artifacts $LOCALREL/igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/
  fi
fi
echo 'CMSSW_PROFILING;OK,Profiling Results,See Logs,profiling' >> ${RESULTS_DIR}/profiling.txt
prepare_upload_results
mark_commit_status_all_prs 'profiling' 'success' -u "${BUILD_URL}" -d "Passed"
