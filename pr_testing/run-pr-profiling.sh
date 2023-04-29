#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

ALLOWED_PROFILING_WORKFLOWS=$(grep "PR_TEST_MATRIX_EXTRAS_PROFILING=" $CMS_BOT_DIR/cmssw-pr-test-config | sed 's|.*=||;s|,| |g')

if [ "X$PROFILING_WORKFLOWS" == "X" ];then
  WORKFLOWS=$ALLOWED_PROFILING_WORKFLOWS
else
  for PROFILING_WORKFLOW in $PROFILING_WORKFLOWS;do
    if echo $ALLOWED_PROFILING_WORKFLOWS | grep -qw $PROFILING_WORKFLOW ; then
      WORKFLOWS="$WORKFLOWS $PROFILING_WORKFLOW"
    else
      echo "Workflow $PROFILING_WORKFLOW not in allowed workflows $ALLOWED_WORKFLOW_LIST"
    fi
  done
fi

git clone --depth 1 https://github.com/cms-cmpwg/profiling.git

for PROFILING_WORKFLOW in $WORKFLOWS;do
  if [ $(runTheMatrix.py -n | grep "^$PROFILING_WORKFLOW " | wc -l) -eq 0 ] ; then
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Not run: not a valid workflows" -e
    continue
  else
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  fi
  mkdir -p $WORKSPACE/upload/profiling/
  echo "<html><head></head><title>Profiling wf $PROFILING_WORKFLOW' results</title><body><ul>" > $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  LOCALREL=${WORKSPACE}/${CMSSW_VERSION}
  export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
  PROF_RES="OK"
  export PROFILING_WORKFLOW
  $WORKSPACE/profiling/Gen_tool/Gen.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_cpu.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_mem_TC.sh $CMSSW_VERSION || true
  if [ ! -d $WORKSPACE/$CMSSW_VERSION/$PROFILING_WORKFLOW ] ; then
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Error: failed to run profiling"
    echo "<li>$PROFILING_WORKFLOW: No such directory</li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
    PROF_RES="ERROR"
    continue
  fi
  pushd $WORKSPACE/$CMSSW_VERSION/$PROFILING_WORKFLOW
  $WORKSPACE/profiling/Gen_tool/profile_igpp.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/profile_igmp.sh $CMSSW_VERSION || true
  echo "<li><a href=\"$PROFILING_WORKFLOW/\">$PROFILING_WORKFLOW/</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/RES_CPU_step3.txt  ${CMSSW_VERSION}_RES_CPU_step3.txt || true
  $WORKSPACE/profiling/Analyze_tool/compare_cpu_txt.py --old ${CMSSW_VERSION}_RES_CPU_step3.txt --new RES_CPU_step3.txt > RES_CPU_compare_$PROFILING_WORKFLOW.txt || true
  echo "<li><a href=\"$PROFILING_WORKFLOW/RES_CPU_compare_$PROFILING_WORKFLOW.txt\">Igprof Comparison cpu usage RECO produce methods.</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  cp $WORKSPACE/cms-bot/comparisons/compareProducts.* ./
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/step3_sizes_${PROFILING_WORKFLOW}.txt  step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt || true
  if [ $(ls -d step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt | wc -l) -gt 0 ]; then
    edmEventSize -v step3*.root > step3_sizes_${PROFILING_WORKFLOW}.txt || true
    ls -l 
    ./compareProducts.sh step3_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt step3_sizes_${PROFILING_WORKFLOW}.txt _ 100 10 > products_AOD_sizes_compare_${PROFILING_WORKFLOW}.txt || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/products_AOD_sizes_compare_${PROFILING_WORKFLOW}.txt\"> edmEventSize Comparison AOD output.</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  fi
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/step4_sizes_${PROFILING_WORKFLOW}.txt  step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt || true
  if [ $(ls -d step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt | wc -l) -gt 0 ]; then
    edmEventSize -v step4*.root > step4_sizes_${PROFILING_WORKFLOW}.txt || true
    ls -l 
    ./compareProducts.sh step4_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt step4_sizes_${PROFILING_WORKFLOW}.txt _ 100 10 > products_miniAOD_sizes_compare_${PROFILING_WORKFLOW}.txt || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/products_miniAOD_sizes_compare_${PROFILING_WORKFLOW}.txt\"> edmEventSize Comparison miniAOD output.</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  fi
  get_jenkins_artifacts igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/step5_sizes_${PROFILING_WORKFLOW}.txt  step5_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt || true
  if [ $(ls -d step5_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt | wc -l) -gt 0 ]; then #DEBUG
    edmEventSize -v step5*.root > step5_sizes_${PROFILING_WORKFLOW}.txt || true
    ls -l 
    ./compareProducts.sh step5_sizes_${CMSSW_VERSION}_${PROFILING_WORKFLOW}.txt step5_sizes_${PROFILING_WORKFLOW}.txt _ 100 10 > products_nanoAOD_sizes_compare_${PROFILING_WORKFLOW}.txt || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/products_nanoAOD_sizes_compare_${PROFILING_WORKFLOW}.txt\"> edmEventSize Comparison nanoAOD output.</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  fi #DEBUG
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
    echo "<li><a href=\"https://cmssdt.cern.ch/SDT/cgi-bin/igprof-navigator/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.sql3/}\"> $(basename $f)</a> </li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.json' ) ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    ln -s /data/sdt/SDT/jenkins-artifacts/pull-request-integration/${UPLOAD_UNIQ_ID}/profiling/$d/$BASENAME $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    ls -l $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/$BASENAME || true
    AMP="&"
    echo "<li><a href=\"https://cmssdt.cern.ch/circles/web/piechart.php?local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.log' -o -name '*.txt' -o -name '*.tmp') ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
  done
  popd
  echo "<br><br>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "</ul></body></html>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  if [ -z ${NO_POST} ] ; then
    if [ -d $LOCALREL/profiling ]; then
      send_jenkins_artifacts $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH} profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/
    fi
    if [ -d $LOCALREL/igprof ]; then
      send_jenkins_artifacts $LOCALREL/igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling igprof/${CMSSW_VERSION}/${SCRAM_ARCH}/profiling/
    fi
  fi
  echo "CMSSW_PROFILING_${PROFILING_WORKFLOW};${PROF_RES},Profiling wf $PROFILING_WORKFLOW Results,See Logs,profiling/index-${PROFILING_WORKFLOW}.html" >> ${RESULTS_DIR}/profiling-$PROFILING_WORKFLOW.txt
  prepare_upload_results
  mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Passed"
done
