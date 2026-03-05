#!/bin/bash -ex
source $(dirname $0)/setup-pr-test-env.sh

ALLOWED_PROFILING_WORKFLOWS=$($CMS_BOT_DIR/cmssw-pr-test-config _PROFILING | tr ',' ' ')
MATRIX_OPT=$($CMS_BOT_DIR/cmssw-pr-test-config _PROFILING MATRIX_OPTION)

if [ "X$PROFILING_WORKFLOWS" == "X" ];then
  WORKFLOWS=$ALLOWED_PROFILING_WORKFLOWS
else
  for PROFILING_WORKFLOW in $(echo $PROFILING_WORKFLOWS | tr ',' ' ') ; do
      WORKFLOWS="$WORKFLOWS $PROFILING_WORKFLOW"
  done
fi


git clone --depth 1 https://github.com/cms-cmpwg/profiling.git

mkdir -p $WORKSPACE/upload/profiling/
for PROFILING_WORKFLOW in $WORKFLOWS;do
  if [ $(runTheMatrix.py -n | grep -w "$PROFILING_WORKFLOW" 2>/dev/null | wc -l) -eq 0 ] ; then
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Not run: not a valid workflows" -e
    echo "<li>$PROFILING_WORKFLOW: Not a valid workflow</li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
    PROF_RES="ERROR"
    echo "CMSSW_PROFILING_${PROFILING_WORKFLOW};${PROF_RES},Profiling wf $PROFILING_WORKFLOW Results,See Logs,profiling/index-${PROFILING_WORKFLOW}.html" >> ${RESULTS_DIR}/profiling-$PROFILING_WORKFLOW.txt
    continue
  else
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'pending' -u "${BUILD_URL}" -d "Running tests" || true
  fi
  echo "<html><head></head><title>Profiling wf $PROFILING_WORKFLOW results</title><body><ul>" > $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  export LOCALREL=${WORKSPACE}/${CMSSW_VERSION}
  export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
  PROF_RES="OK"
  $CMS_BOT_DIR/das-utils/use-ibeos-sort || true
  export PROFILING_WORKFLOW
  $WORKSPACE/profiling/Gen_tool/Gen.sh $CMSSW_VERSION || true
  export RUNALLSTEPS=1
  $WORKSPACE/profiling/Gen_tool/runall.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_allocmon.sh $CMSSW_VERSION || true
  $WORKSPACE/profiling/Gen_tool/runall_vtune.sh $CMSSW_VERSION || true
  if [ ! -d $WORKSPACE/$CMSSW_VERSION/$PROFILING_WORKFLOW ] ; then
    mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Error: failed to run profiling"
    echo "<li>$PROFILING_WORKFLOW: No such directory</li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
    PROF_RES="ERROR"
    continue
  fi
  WAIT_TIME=36000
  while [ $WAIT_TIME -gt 0 ] ; do
    if  has_jenkins_artifacts profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/$PROFILING_WORKFLOW/moduleAllocMonitor.log  ; then
      break
    else
      sleep 60
      let WAIT_TIME=$WAIT_TIME-60
    fi
  done
  pushd $WORKSPACE/$CMSSW_VERSION/ || true
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_cpu.resources.json' | sort -V ) ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    cp -p $f $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/ || true
    AMP="&"
    echo "<li><a href=\"https://cmssdt.cern.ch/circles/web/piechart.php?data_name=profiling${AMP}filter=${CMSSW_VERSION}${AMP}local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_cpu.resources.json' | sort -V ) ; do
    BASENAME=$(basename $f)
    get_jenkins_artifacts profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/$f $PWD/$CMSSW_VERSION-$BASENAME || true
    if ! [ -f $PWD/$CMSSW_VERSION-$BASENAME ] ; then
      echo "<li>File $CMSSW_VERSION-$BASENAME not found, skipping diff</li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
      continue
    fi
    $CMS_BOT_DIR/comparisons/resources-diff.py $CMSSW_VERSION-$BASENAME $f >$f.log || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/diff-$BASENAME.html\">diff-$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_moduleAllocMonitor.circles.json'| sort -V ) ; do
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    cp -p $f $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/ || true
    AMP="&"
    echo "<li><a href=\"https://cmssdt.cern.ch/circles/web/piechart.php?data_name=profiling${AMP}filter=${CMSSW_VERSION}${AMP}local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_moduleAllocMonitor.circles.json'| sort -V ) ; do
    BASENAME=$(basename $f)
    get_jenkins_artifacts profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/$f $PWD/$CMSSW_VERSION-$BASENAME || true
    if ! [ -f $PWD/$CMSSW_VERSION-$BASENAME ] ; then
      echo "<li>File $CMSSW_VERSION-$BASENAME not found, skipping diff</li>">> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
      continue
    fi
    $CMS_BOT_DIR/comparisons/moduleAllocMonitor-circles-diff.py $CMSSW_VERSION-$BASENAME $f >$f.log || true
    echo "<li><a href=\"${PROFILING_WORKFLOW}/diff-$BASENAME.html\">diff-$BASENAME</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.json.gz' -o -name '*.log' -o -name '*.txt' -o -name '*.tmp' -o -name '*.heap*' -o -name '*.json' -o -name '*.html' | grep -v 'r-step') ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
  done
  for d in $(find $PROFILING_WORKFLOW -type d -name 'r-step*' | sort -V ) ; do
    mkdir -p $WORKSPACE/vtune-profiles/$d || true
    rsync -auv $d/ $WORKSPACE/vtune-profiles/$d/ || true
    echo "<li><a href=\"https://cmssdt.cern.ch/vtune/ui/$CMSSW_VERSION/$ARCHITECTURE/$PROFILING_WORKFLOW/$UPLOAD_UNIQ_ID/$(basename $d)\">$(basename $d)</a></li>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  popd
  echo "<br><br>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "</ul></body></html>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  if [ -z ${NO_POST} ] ; then
    if [ -d $LOCALREL/profiling ]; then
      send_jenkins_artifacts $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH} profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/
    fi
  fi
  echo "CMSSW_PROFILING_${PROFILING_WORKFLOW};${PROF_RES},Profiling wf $PROFILING_WORKFLOW Results,See Logs,profiling/index-${PROFILING_WORKFLOW}.html" >> ${RESULTS_DIR}/profiling-$PROFILING_WORKFLOW.txt
  prepare_upload_results
  mark_commit_status_all_prs "profiling wf $PROFILING_WORKFLOW" 'success' -u "${BUILD_URL}" -d "Passed"
done

ARTIFACTS_SERVER=cmsvtune-01.cern.ch
ARTIFACTS_USER=vtune
ARTIFACT_BASE_DIR=/data/cms
source $CMS_BOT_DIR/jenkins-artifacts
for WORKFLOW in $WORKFLOWS ; do
  if [ -d $WORKSPACE/vtune-profiles/${WORKFLOW} ]; then
    send_jenkins_artifacts $WORKSPACE/vtune-profiles/${WORKFLOW} vtune-profiles/$CMSSW_VERSION/$ARCHITECTURE/${WORKFLOW}/$UPLOAD_UNIQ_ID
  fi
done

