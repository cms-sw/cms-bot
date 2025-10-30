#!/bin/bash -ex
source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

PR_REPO_NUM=$(echo $PULL_REQUEST | sed 's|^.*/||;s|#||')
UPLOAD_PATH="${CMSSW_VERSION}-${PR_REPO_NUM}/${ARCHITECTURE}/${BUILD_NUMBER}"
# Report test started
mark_commit_status_all_prs 'hlt-p2-integration' 'pending' -u "${BUILD_URL}" -d "Running"

# Do work
HLT_P2_SCRIPT="src/HLTrigger/Configuration/scripts"
HLT_BASEDIR="${CMSSW_BASE}"
if [ ! -e "${HLT_BASEDIR}/${HLT_P2_SCRIPT}" ] ; then HLT_BASEDIR="${CMSSW_RELEASE_BASE}" ; fi
cp -r ${HLT_BASEDIR}/${HLT_P2_SCRIPT} $WORKSPACE/rundir
rm -rf $WORKSPACE/rundir/__pycache__

INTEGRTESTS_LOG="${WORKSPACE}/hlt-p2-integration.log"

HLT_P2_RES="SUCCESS"

pushd $WORKSPACE/rundir
    set -o pipefail # required for correct error status piping within the loop
    export LOCALRT=${WORKSPACE}/${CMSSW_VERSION}
	if hltPhase2UpgradeIntegrationTests --help | grep -w -- "--menu " 2>/dev/null ; then # if the "--menu" option is included in this IB
		for elem in $(python3 -c 'from Configuration.HLT.autoHLT import autoHLT; [print(v) for k,v in autoHLT.items() if "Run4" in k]') ; do
			timeout $TIMEOUT hltPhase2UpgradeIntegrationTests --menu ${elem} --parallelJobs $(nproc) 2>&1 | tee -a ${INTEGRTESTS_LOG} || HLT_P2_RES="ERROR"
		done
	else # if the "--menu" option is NOT included in this IB
		timeout $TIMEOUT hltPhase2UpgradeIntegrationTests --parallelJobs $(nproc) 2>&1 | tee -a ${INTEGRTESTS_LOG}
	fi
	set +o pipefail
popd

# Upload results
source $WORKSPACE/cms-bot/jenkins-artifacts
touch ${RESULTS_DIR}/11-hlt-p2-integration-failed.res

if grep -iE 'Error|failure' "${INTEGRTESTS_LOG}"; then
  HLT_P2_RES="ERROR"
elif [ ! -f $WORKSPACE/rundir/Phase2Timing_resources.json ] ; then
  HLT_P2_RES="ERROR"
fi
echo "HLT_P2_INTEGRATION;${HLT_P2_RES},HLT Phase 2 integration Test,See Logs,hlt-p2-integration.log" >> ${RESULTS_DIR}/hlt-p2-integration.txt

if [ "${HLT_P2_RES}" = "SUCCESS" ] ; then
    mark_commit_status_all_prs 'hlt-p2-integration' 'success' -u "${BUILD_URL}" -d "HLT Phase2 integration data collected"
else
  echo "HLTP2Integration" > ${RESULTS_DIR}/11-hlt-p2-integration-failed.res
  mark_commit_status_all_prs 'hlt-p2-integration' 'error' -u "${BUILD_URL}" -d "HLT Phase2 integration script failed"
fi

rm -rf $WORKSPACE/json_upload $WORKSPACE/rundir
prepare_upload_results
