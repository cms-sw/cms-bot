#!/bin/bash -ex

IB=$1
STEP=$2
WF=$3
O2=$4
LOCAL_DATA=$5
RUNS=$6
EVENTS=$7
THREADS=$8

function cmsenv()
{
  set +x ; eval `scram run -sh` >/dev/null 2>&1 ; set -x
}

function create_local_installation()
{
  if [ ! -d cmssw ] ; then
    mkdir cmssw && cd cmssw
    wget -O bootstrap.sh http://cmsrep.cern.ch/cmssw/repos/bootstrap.sh
    export SCRAM_ARCH=el8_amd64_gcc12
    sh -x bootstrap.sh setup -path $(pwd) -arch $SCRAM_ARCH >& $(pwd)/bootstrap_$SCRAM_ARCH.log
    common/cmspkg -a $SCRAM_ARCH update
    common/cmspkg -a $SCRAM_ARCH install -y -r cms.lto cms+cmssw+${IB}
    cd ..
  fi
  source cmssw/cmsset_default.sh
  scram list CMSSW
}

function create_development_area()
{
  # This function is used to change LTO flags and build CMSSW locally from an IB
  if [ ! -d ${IB} ] ; then
    scram p ${IB}
    cd ${IB}/src
    cmsenv
    git cms-addpkg '*'
    cd ..
    if [[ "X$O2" == "Xtrue" ]]; then
        echo "*** USING -O2 OPTIMIZATION ***"
        TYPE="${TYPE}-O2"
        find config/toolbox/el8_amd64_gcc12/tools/selected/ -type f -name 'gcc-*.xml' -exec sed -i 's/O3/O2/g' {} \;
        for tool in $(find . -type f -name 'gcc-*.xml' | rev | cut -d "/" -f1 | rev | cut -d "." -f1); do
	    scram setup $tool
	done
	find config/toolbox/el8_amd64_gcc12/tools/selected/ -type f -name 'cuda.xml' -exec sed -i 's/O3/O2/g' {} \; && scram setup cuda
    else
        echo "*** USING -O3 OPTIMIZATION ***"
        TYPE="${TYPE}-O3"
    fi
    cd ..
    echo "*** BUILDING CMSSW FOR ${TYPE}***"
    scram build -j 16
  fi
}

function create_development_area_for_release()
{
  if [ ! -d ${IB} ] ; then
    scram p ${IB}
    cd ${IB}/src
    cmsenv
    cd ..
  fi
}

function create_development_area_for_release_hlt()
{
  if [ ! -d ${IB} ] ; then
    scram p ${IB}
    cd ${IB}/src
    cmsenv
    git cms-addpkg HLTrigger/Configuration
    cd ..
    # TODO: For now, data should be copied locally on the node. Otherwise, uncommment:
    #mkdir -p /data/user/cmsbld//store/relval/CMSSW_14_1_0_pre6/RelValTTbar_14TeV/GEN-SIM-DIGI-RAW/PU_141X_mcRun4_realistic_v1_STD_2026D110_PU-v3/2810000
    #scp -r cmsbuild@srv-b1b07-18-01.cern.ch:/data/user/cmsbuild//store/relval/CMSSW_14_1_0_pre6/RelValTTbar_14TeV/GEN-SIM-DIGI-RAW/PU_141X_mcRun4_realistic_v1_STD_2026D110_PU-v3/2810000/*.root /data/user/cmsbld//store/relval/CMSSW_14_1_0_pre6/RelValTTbar_14TeV/GEN-SIM-DIGI-RAW/PU_141X_mcRun4_realistic_v1_STD_2026D110_PU-v3/2810000
  fi
}

echo "*** INSTALLING RELEASE LOCALLY ***"
TYPE="LTO"
if [[ "${IB}" == *"NONLTO"* ]]; then
  TYPE="NONLTO"
fi
if [[ "${IB}" == *"O2"* ]]; then
  TYPE="O2${TYPE}"
else
  TYPE="O3${TYPE}"
fi

create_local_installation
export SITECONFIG_PATH=/cvmfs/cms.cern.ch/SITECONF/T2_CH_CERN
echo "*** CREATING DEVELOPMENT AREA ***"
if [[ "${STEP}" == *"hlt"* ]]; then
  create_development_area_for_release_hlt
else
  create_development_area_for_release
fi
echo "*** RUNNING WF TO DUMP CONFIG FILES ***"
mkdir relvals && mkdir data && cd data

voms-proxy-init -voms cms -rfc
# TODO: Add option for step1 (we need a generator card to control the generated events)
if [[ "${STEP}" == *"step3"* ]]; then
  runTheMatrix.py -l $WF -t ${THREADS} --maxSteps 3 --nEvents ${EVENTS} --ibeos -i all --job-reports --command "  --customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary"
  cp ${WF}*/step3*.py ../relvals
  cp ${WF}*/step2*.root ../relvals
elif [[ "${STEP}" == *"hlt"* ]]; then
  cd ../src/HLTrigger/Configuration/python/HLT_75e33/test
  /usr/bin/time --verbose ./runHLTTiming.sh > setup-run.log 2>&1
  for x in 1 2 3 4 5; do
    # TODO: Modify the default number of events according to the user input (default: 1k events)
    /usr/bin/time --verbose cmsRun --numThreads ${THREADS} Phase2_L1P2GT_HLT.py >> run.log 2>&1
    cat run.log | grep "Elapsed " || true
  done
  result=$(cat run.log | grep "Elapsed " | awk '{print $8}' | paste -sd,)
  echo "hlt_${EVENTS}events_${THREADS}threads_time = [$result]"
  echo "hlt_${EVENTS}events_${THREADS}threads_time = [$result]" >> summary.log
  cat summary.log
  exit 0
else # Run all the steps
  runTheMatrix.py -l $WF -t ${THREADS} --ibeos --job-reports  --command "  --customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary"
  cp -r ${WF}*/*.py ../relvals
fi

cd ${WF}*

if [[ "X$LOCAL_DATA" == "Xtrue" ]]; then
  echo "COPYING DATA"
  # Parse logs to get the data
  for logfiles in $(ls ${STEP}*.log); do
    for file in $(grep "Successfully opened file" $logfiles | grep -o 'root://[^ ]*'); do
      echo "--> ${file}"
      local_path=$(echo ${file} | sed 's/.*\(store\/.*\)/\1/')
      mkdir -p $(dirname ${local_path})
      xrdcopy ${file} ${local_path} || true
    done
  done
  # Parse config files to get the data
  for configfiles in $(ls ${STEP}*.py); do
    datafiles=$(grep "process.mix.input.fileNames" $configfiles | cut -d "[" -f2 | cut -d "]" -f1 | tr -d "'")
    xrootdprefix="root://eoscms.cern.ch//eos/cms/store/user/cmsbuild/"
    for file in ${datafiles//,/ }; do
      echo "--> $file"
      local_path=$(echo ${file} | sed 's/.*\(store\/.*\)/\1/')
      mkdir -p $(dirname ${local_path})
      xrootdfile=$(echo $file | cut -d : -f2)
      xrdcopy ${xrootdprefix}${xrootdfile} ${local_path} || true
    done
  done
  mv store ../../relvals
fi

cd ../../relvals

echo "*** RUNNING WF STEPS ***"
for x in 1 2 3 4 5; do
  for files in $(ls ${STEP}*.py); do
    if [ ${x} -eq 1 ]; then
      echo "[DBG] Modifying number of events to a 100"
      sed -i "s/(10)/(${EVENTS})/g" $files
      if [[ "X$LOCAL_DATA" == "Xtrue" ]]; then
	sed -i "s/\/store/file:store/g" $files
      fi
      cat $files | grep "file:store" || true
      cat $files | grep "(100)" || true
    fi
    file_name=$(echo $files | cut -d "." -f1)
    echo "--> ${file_name}"
    SHORT_WF=$(echo $WF | cut -d "." -f1)
    /usr/bin/time --verbose cmsRun --numThreads ${THREADS} $files >> "${STEP}_${SHORT_WF}_${TYPE}_${file_name}.logfile" 2>&1
    cat "${STEP}_${SHORT_WF}_${TYPE}_${file_name}.logfile" | grep "Elapsed "
    cat "${STEP}_${SHORT_WF}_${TYPE}_${file_name}.logfile" | grep "Event Throughput"
  done
done

echo "--- TIME SUMMARY ---"
for files in $(ls *.logfile); do
  file_name=$(echo $files | cut -d "." -f1-2 | cut -d "_" -f1-3)
  result=$(cat ${files} | grep "Elapsed " | awk '{print $8}' | paste -sd,)
  echo "${file_name}_time = [$result]" >> summary.log
done

echo "--- EVENT THROUGHPUT SUMMARY ---"
for files in $(ls *.logfile); do
  file_name=$(echo $files | cut -d "." -f1-2 | cut -d "_" -f1-3)
  result=$(cat ${files} | grep "Event Throughput" | awk '{print $3}' | paste -sd,)
  echo "${file_name}_tp = [$result]" >> summary.log
done
