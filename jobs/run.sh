#!/bin/bash
eval `scram run -sh`
cd ${CMSSW_BASE}
export PATH=${CMSSW_BASE}/cms-bot/das-utils:${PATH}
export PYTHONUNBUFFERED=1
export CMS_PATH=/cvmfs/cms-ib.cern.ch
export SITECONFIG_PATH=/cvmfs/cms-ib.cern.ch/SITECONF/local
voms-proxy-init -voms cms

rm -rf all-pyRelval
mkdir all-pyRelval
for wfs in $(ls wf*of*) ; do
  rm -rf pyRelval*
  ${CMSSW_BASE}/cms-bot/jobs/create-relval-jobs.py $(cat $wfs)
  for type in cpu rss dynamic time ; do
    cp -r pyRelval pyRelval-${type}
    pushd pyRelval-${type}
      ${CMSSW_BASE}/cms-bot/jobs/jobscheduler.py -c 200 -m 95 -o ${type}
    popd
    mv pyRelval-${type} all-pyRelval/${wfs}-${type}
    sleep 600
  done
  rm -rf pyRelval*
  sleep 1200
done
