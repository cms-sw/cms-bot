#!/bin/bash

# Function to set template-specific parameters
set_template_params() {
  case "$1" in
    HYBRID)
      EFFI_THRESHOLD="96.3"
      EFFI_HISTORIC="96.5"
      NTRK_THRESHOLD="29"
      NTRK_HISTORIC="27"
      Z0RES_THRESHOLD="0.40"
      Z0RES_HISTORIC="0.36"
      ;;
    HYBRID_NEWKF)
      EFFI_THRESHOLD="95.7"
      EFFI_HISTORIC="95.9"
      NTRK_THRESHOLD="33"
      NTRK_HISTORIC="31"
      Z0RES_THRESHOLD="1.00"
      Z0RES_HISTORIC="0.87"
      ;;
    HYBRID_DISPLACED)
      EFFI_THRESHOLD="97.3"
      EFFI_HISTORIC="97.5"
      NTRK_THRESHOLD="40"
      NTRK_HISTORIC="37"
      Z0RES_THRESHOLD="0.40"
      Z0RES_HISTORIC="0.36"
      ;;
    *)
      echo "Unknown algo: $1"
      exit 1
      ;;
  esac
}

source $WORKSPACE/cms-bot/pr_testing/setup-pr-test-env.sh

# Main script starts here
if [ -z "$1" ]; then
  echo "Usage: $0 <template_name>"
  exit 1
fi

L1TRKALGO=$1
LOGFILE=$L1TRKALGO.log
set_template_params "$L1TRKALGO"

# Extra Parameters
MC_DATASET="https://cernbox.cern.ch/remote.php/dav/public-files/4wMLEX986bdIs8U/skimmedForCI_14_0_0.root"
MC_DESCRIPTION="1k events RelVal_1400_D98_PU0_TTbar"

# Begin script
echo "Will run the L1 track algo = $L1TRKALGO" | tee $LOGFILE

JOBNAME="job_${L1TRKALGO}_cfg.py"
cp $CMSSW_BASE/src/L1Trigger/TrackFindingTracklet/test/L1TrackNtupleMaker_cfg.py "$JOBNAME"
sed -i "s|L1TRKALGO = 'HYBRID'|L1TRKALGO = '$L1TRKALGO'|" "$JOBNAME"
grep L1TRKALGO "$JOBNAME" # Check setting algo successful

RESULTSDIR="results_${L1TRKALGO}"
mkdir -p "$RESULTSDIR"

echo "=== Get MC dataset $MC_DATASET ===" | tee $LOGFILE
curl -k -o mc_dataset.root "$MC_DATASET"
ls -l

echo "=== Run L1 tracking CMSSW job ===" | tee $LOGFILE
{
    echo "process.source.fileNames = cms.untracked.vstring('file:mc_dataset.root')"
    echo "process.maxEvents = cms.untracked.PSet(input = cms.untracked.int32(1000))"
    echo "process.TFileService.fileName = '$RESULTSDIR/histos.root'"
} >> "$JOBNAME"

cmsRun "$JOBNAME"
ls -l
rm mc_dataset.root

cd "$RESULTSDIR" || exit
ls -l
echo "=== Results algo $L1TRKALGO run on MC $MC_DESCRIPTION ===" | tee $LOGFILE
$CMSSW_BASE/src/L1Trigger/TrackFindingTracklet/test/makeHists.csh histos.root # Create output histograms & results.out file.

# Check tracking efficiency exceeds threshold
EFFI=$(grep "combined efficiency" results.out | cut -f2 -d= | cut -f1 -d+)
FAILeff=$(echo "$EFFI < $EFFI_THRESHOLD" | bc)
MESS_FAIL="FAILURE -- TRACKING EFFICIENCY TOO LOW $EFFI < $EFFI_THRESHOLD"
MESS_OK="SUCCESS -- TRACKING EFFICIENCY ACCEPTABLE $EFFI > $EFFI_THRESHOLD"
if (( FAILeff )); then
    echo "$MESS_FAIL" | tee $LOGFILE
else
    echo "$MESS_OK" | tee $LOGFILE
fi
echo "Historic tracking efficiency (for comparison) = $EFFI_HISTORIC" | tee $LOGFILE

# Check no. of tracks below threshold
NTRK=$(grep "tracks/event (pt > 2.0" results.out | cut -f2 -d=)
FAILntrk=$(echo "$NTRK > $NTRK_THRESHOLD" | bc)
MESS_FAIL="FAILURE -- TOO MANY TRACKS $NTRK > $NTRK_THRESHOLD"
MESS_OK="SUCCESS -- NUM TRACKS OK $NTRK < $NTRK_THRESHOLD"
if (( FAILntrk )); then
    echo "$MESS_FAIL" | tee $LOGFILE
else
    echo "$MESS_OK" | tee $LOGFILE
fi
echo "Historic no. of tracks (for comparison) = $NTRK_HISTORIC" | tee $LOGFILE

# Check z0 resolution below threshold
Z0RES=$(grep "z0 resolution" results.out | grep "|eta| = 1.95" | cut -f2 -d= | cut -f1 -dc)
FAILz0=$(echo "$Z0RES > $Z0RES_THRESHOLD" | bc)
MESS_FAIL="FAILURE -- BAD Z0 RESOLUTION $Z0RES > $Z0RES_THRESHOLD"
MESS_OK="SUCCESS -- GOOD Z0 RESOLUTION $Z0RES < $Z0RES_THRESHOLD"
if (( FAILz0 )); then
    echo "$MESS_FAIL" | tee $LOGFILE
else
    echo "$MESS_OK" | tee $LOGFILE
fi
echo "Historic z0 resolution (for comparison) = $Z0RES_HISTORIC" | tee $LOGFILE

# Overall check result
FAIL=$(echo "$FAILeff || $FAILntrk || $FAILz0" | bc)
MESS_FAIL="FAILURE -- SOME CHECKS FAILED"
MESS_OK="SUCCESS -- ALL CHECKS PASSED"
if (( FAIL )); then
    echo "$MESS_FAIL" | tee $LOGFILE
else
    echo "$MESS_OK" | tee $LOGFILE
fi

exit "$FAIL"
