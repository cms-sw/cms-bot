#!/bin/bash -ex
echo "FAILED" > $WORKSPACE/testsResults/statusfile-hlt-p2-timing.log

if [ "${SINGULARITY_IMAGE}" = "" ] ; then
  osver=$(echo ${SCRAM_ARCH} | tr '_' '\n' | head -1 | sed 's|^[a-z][a-z]*||')
  ls /cvmfs/singularity.opensciencegrid.org >/dev/null 2>&1 || true
  IMG_PATH="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel${osver}"
  if [ ! -e "${IMG_PATH}" ] ; then
    IMG_PATH="/cvmfs/unpacked.cern.ch/registry.hub.docker.com/${DOCKER_IMG}"
  fi
  export SINGULARITY_IMAGE="${IMG_PATH}"
fi

[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE
mkdir -p $WORKSPACE/testsResults
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh
source $WORKSPACE/cms-bot/common/github_reports.sh

# Report test started
mark_commit_status_all_prs 'hlt-p2-timing' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
timeout $TIMEOUT ${CMSSW_CVMFS_PATH}/src/HLTrigger/Configuration/python/HLT_75e33/test/runHLTTiming.sh 2>&1 | tee $WORKSPACE/hlt-p2-timing.log

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
if [ -f $WORKSPACE/Phase2Timing_resources.json ] ; then
  echo "PASSED" > $WORKSPACE/statusfile-hlt-p2-timing.log
  touch $WORKSPACE/testsResults/hlt-p2-timing-failed-${CRABCLIENT_TYPE}.res
  touch $WORKSPACE/testsResults/hlt-p2-timing-report-${CRABCLIENT_TYPE}.res

  mv WORKSPACE/Phase2Timing_resources*.json $WORKSPACE/testsResults
  mark_commit_status_all_prs 'hlt-p2-timing' 'success' -u "${BUILD_URL}" -d "HLT Phase2 timing data collected"
else
  echo "HLT_P2_TIMING;ERROR,HLT Phase 2 timing Test,See Logs,hlt-p2-timing.log" >> $WORKSPACE/testsResults/hlt-p2-timing.txt
  echo "HLT_P2_TIMING" > $WORKSPACE/testsResults/hlt-p2-timing-failed.res

  mark_commit_status_all_prs 'hlt-p2-timing' 'error' -u "${BUILD_URL}" -d "HLT Phase2 timing script failed"
fi

prepare_upload_results

# TODO: how to post a link for a successfull build? How to show it on /summary.html?
