#!/bin/bash -ex

trap report EXIT

report() {
   exit_code=$?
   if [ ${exit_code} -ne 0 ]; then
       echo "FAILED" > $WORKSPACE/crab/statusfile
   fi
}

#Checkout a package
git cms-addpkg FWCore/Version
#Added test python module and script to make sure it is part of card sandbox
mkdir -p ${CMSSW_BASE}/src/FWCore/Version/python ${CMSSW_BASE}/src/FWCore/Version/scripts
echo 'CMSBOT_CRAB_TEST="OK"' > ${CMSSW_BASE}/src/FWCore/Version/python/cmsbot_crab_test.py
echo -e '#!/bin/bash\necho OK' > ${CMSSW_BASE}/src/FWCore/Version/scripts/cmsbot_crab_test.sh
chmod +x ${CMSSW_BASE}/src/FWCore/Version/scripts/cmsbot_crab_test.sh
scram build -j $(nproc)

[ "${CRABCLIENT_TYPE}" != "" ]   || export CRABCLIENT_TYPE="prod"
[ "${BUILD_ID}" != "" ]          || export BUILD_ID=$(date +%s)
[ "${WORKSPACE}" != "" ]         || export WORKSPACE=$(pwd) && cd $WORKSPACE
[ "${CRABCONFIGINSTANCE}" != "" ]|| export CRABCONFIGINSTANCE="prod"

if [ "${SINGULARITY_IMAGE}" = "" ] ; then
  osver=$(echo ${SCRAM_ARCH} | tr '_' '\n' | head -1 | sed 's|^[a-z][a-z]*||')
  ls /cvmfs/singularity.opensciencegrid.org >/dev/null 2>&1 || true
  IMG_PATH="/cvmfs/singularity.opensciencegrid.org/cmssw/cms:rhel${osver}"
  if [ ! -e "${IMG_PATH}" ] ; then
    IMG_PATH="/cvmfs/unpacked.cern.ch/registry.hub.docker.com/${DOCKER_IMG}"
  fi
  export SINGULARITY_IMAGE="${IMG_PATH}"
fi

export CRAB_REQUEST="Jenkins_${CMSSW_VERSION}_${SCRAM_ARCH}_${BUILD_ID}"
cmssw_queue=$(echo ${CMSSW_VERSION} | cut -d_ -f1-3)_X
thisdir=$(dirname $0)
if [ -e ${thisdir}/${cmssw_queue}/pset.py ] ; then
  export CMSRUN_PSET=${thisdir}/${cmssw_queue}/pset.py
else
  export CMSRUN_PSET=${thisdir}/pset.py
fi
[ "${X509_USER_PROXY}" = "" ] && voms-proxy-init -voms cms
x509proxy=$(voms-proxy-info -path)
pyver=$(${CMSBOT_PYTHON_CMD} -c 'import sys;print("python%s%s" % (sys.version_info[0],sys.version_info[1]))')
if [ -e ${thisdir}/${pyver} ] ; then export PYTHONPATH="${thisdir}/${pyver}:${PYTHONPATH}"; fi
crab submit --proxy ${x509proxy} -c ${thisdir}/task.py
rm -rf ${WORKSPACE}/crab
mv crab_${CRAB_REQUEST} ${WORKSPACE}/crab
echo "INPROGRESS" > $WORKSPACE/crab/statusfile

cat $WORKSPACE/crab/.requestcache 
export ID=$(id -u)
export TASK_ID=$(grep crab_${CRAB_REQUEST} $WORKSPACE/crab/.requestcache | sed 's|^V||')

if [ "${TASK_ID}" = "" ] ; then exit 1 ; fi

echo "Keep checking job information until grid site has been assigned"
GRIDSITE="N/Ayet"
while [ "${GRIDSITE}" = "N/Ayet" ]
do
  sleep 10
  echo "Gridsite has not been assigned yet!"
  export GRIDSITE=$(crab status --proxy ${x509proxy} -d ./crab | grep "Grid scheduler - Task Worker:" | cut -d ":" -f2 | cut -d "-" -f1 | tr -d '\t' | tr -d " ")
done

# Store information for the monitoring job
echo "CRAB_BUILD_ID=$BUILD_ID" >> $WORKSPACE/crab/parameters.property
GRIDSITE_NAME="http://$(echo $GRIDSITE | cut -d "@" -f2)/mon/cmsbot/${TASK_ID}"
echo "CRAB_GRIDSITE=$GRIDSITE_NAME" >> $WORKSPACE/crab/parameters.property
echo "RELEASE_FORMAT=$RELEASE_FORMAT" >> $WORKSPACE/crab/parameters.property
echo "ARCHITECTURE=$ARCHITECTURE" >> $WORKSPACE/crab/parameters.property
echo "PULL_REQUESTS=$PULL_REQUESTS" >> $WORKSPACE/crab/parameters.property
echo "PULL_REQUEST=$PULL_REQUEST" >> $WORKSPACE/crab/parameters.property
echo "PR_RESULT_URL=$PR_RESULT_URL" >> $WORKSPACE/crab/parameters.property
echo "ENV_LAST_PR_COMMIT=$LAST_PR_COMMIT" >> $WORKSPACE/crab/parameters.property
echo "CMSSW_QUEUE=$CMSSW_QUEUE" >> $WORKSPACE/crab/parameters.property
echo "CONTEXT_PREFIX=$CONTEXT_PREFIX" >> $WORKSPACE/crab/parameters.property
echo "UPLOAD_UNIQ_ID=$UPLOAD_UNIQ_ID" >> $WORKSPACE/crab/parameters.property
[ "$CRAB_SITE" = "" ] || echo "CRAB_SITE=$CRAB_SITE" >> $WORKSPACE/crab/parameters.property
