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
  cat << EOF > $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html 
<html><head>
<style>table, th, td {border: 1px solid black;}</style>
<style> th, td {padding: 15px;}</style>
<style> tr:hover {background-color: #eff3ff}</style>
<style> .noborder {}</style></head>
<title>Profiling Workflow '$PROFILING_WORKFLOW' results</title>
<body>
<h3>Summary of Pull Request Profiling for Workflow $PROFILING_WORKFLOW and comparison to IB $CMSSW_VERSION</h3>
<table>
<tr>
<th align="center">Profiling Test</th>
<th align="center">Step1</th>
<th align="center">Step2</th>
<th align="center">Step3</th>
<th align="center">Step4</th>
<th align="center">Step5</th>
<th align="center">Step6</th>
<th align="center">Step7</th>
<th align="center">Step8</th>
<th align="center">Step9</th>
<th align="center">Step10</th>
<th align="center">Step11</th>
</tr>
EOF
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
    echo "<BR>$PROFILING_WORKFLOW: No such directory" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
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
  echo "<tr><td>Fast Timer Service PR</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_cpu.resources.json' | sort -V ) ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    cp -p $f $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/ || true
    AMP="&"
    echo "<td><a target=\"_blank\" href=\"/circles/web/piechart.php?data_name=profiling${AMP}filter=${CMSSW_VERSION}${AMP}local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  echo "</tr>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "<tr><td>Fast Timer Service PR Comparison to IB</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_cpu.resources.json' | sort -V ) ; do
    BASENAME=$(basename $f)
    get_jenkins_artifacts profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/$f $PWD/$CMSSW_VERSION-$BASENAME || true
    if ! [ -f $PWD/$CMSSW_VERSION-$BASENAME ] ; then
      echo "<td>IB file not found, skipping diff</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
      continue
    fi
    $CMS_BOT_DIR/comparisons/resources-diff.py $CMSSW_VERSION-$BASENAME $f >$f.log || true
    echo "<td><a target=\"_blank\" href=\"${PROFILING_WORKFLOW}/diff-$BASENAME.html\">diff-$BASENAME</a></td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  echo "</tr>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "<tr><td>Module Alloc Monitor PR</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_moduleAllocMonitor.circles.json'| sort -V ) ; do
    BASENAME=$(basename $f)
    mkdir -p $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID} || true
    cp -p $f $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/ || true
    AMP="&"
    echo "<td><a target=\"_blank\" href=\"/circles/web/piechart.php?data_name=profiling${AMP}filter=${CMSSW_VERSION}${AMP}local=false${AMP}dataset=${CMSSW_VERSION}/${SCRAM_ARCH}/${PROFILING_WORKFLOW}/${UPLOAD_UNIQ_ID}/${BASENAME//.json/}${AMP}resource=time_thread${AMP}colours=default${AMP}groups=reco_PhaseII${AMP}threshold=0\">$BASENAME</a></td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  done
  echo "</tr>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "<tr><td>Module Alloc Monitor PR Comparison to IB</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for f in $(find $PROFILING_WORKFLOW -type f -name 'step*_moduleAllocMonitor.circles.json'| sort -V ) ; do
    BASENAME=$(basename $f)
    get_jenkins_artifacts profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/$f $PWD/$CMSSW_VERSION-$BASENAME || true
    if ! [ -f $PWD/$CMSSW_VERSION-$BASENAME ] ; then
      echo "<td>IB file not found, skipping diff</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
      continue
    fi
    $CMS_BOT_DIR/comparisons/moduleAllocMonitor-circles-diff.py $CMSSW_VERSION-$BASENAME $f >$f.log || true
    echo "<td><a target=\"_blank\" href=\"${PROFILING_WORKFLOW}/diff-$BASENAME.html\">diff-$BASENAME</a></td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  echo "</tr>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for f in $(find $PROFILING_WORKFLOW -type f -name '*.json.gz' -o -name '*.log' -o -name '*.txt' -o -name '*.tmp' -o -name '*.heap*' -o -name '*.json' -o -name '*.html' | grep -v 'r-step') ; do
    d=$(dirname $f)
    mkdir -p $WORKSPACE/upload/profiling/$d || true
    cp -p $f $WORKSPACE/upload/profiling/$d/ || true
  done
  echo "<tr><td>Vtune Profiles for PR</td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  for d in $(find $PROFILING_WORKFLOW -type d -name 'r-step*' | sort -V ) ; do
    mkdir -p $WORKSPACE/vtune-profiles/$d || true
    rsync -auv $d/ $WORKSPACE/vtune-profiles/$d/ || true
    echo "<td><a target=\"_blank\" rel=\"noopener noreferrer\" href=\"/vtune/ui/$CMSSW_VERSION/$ARCHITECTURE/$PROFILING_WORKFLOW/$UPLOAD_UNIQ_ID/$(basename $d)\">$(basename $d)/</a></td>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html || true
  done
  echo "</tr>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  popd
  echo "</table>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "<a href=\"$PROFILING_WORKFLOW\"> profiling logs</a>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  echo "</body></html>" >> $WORKSPACE/upload/profiling/index-$PROFILING_WORKFLOW.html
  if [ -z ${NO_POST} ] ; then
    if [ -d $LOCALREL/profiling ]; then
      send_jenkins_artifacts $LOCALREL/profiling/${CMSSW_VERSION}/${SCRAM_ARCH} profiling/${CMSSW_VERSION}/${SCRAM_ARCH}/
    fi
  fi
  echo "CMSSW_PROFILING_${PROFILING_WORKFLOW};${PROF_RES},Profiling workflow $PROFILING_WORKFLOW Results,See Logs,profiling/index-${PROFILING_WORKFLOW}.html" >> ${RESULTS_DIR}/profiling-$PROFILING_WORKFLOW.txt
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

