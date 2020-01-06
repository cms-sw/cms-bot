#!/bin/bash
cat <<EOF
#!/bin/bash -ex
klist || true
kinit -R || true
hostname
cvmfs_config probe || true
for cvmfs_dir in \$(grep CVMFS_REPOSITORIES= /etc/cvmfs/default.local | sed "s|.*=||;s|'||g" | sed 's|"||g' | tr ',' '\n'  | grep cern.ch) ; do
  ls -l /cvmfs/\${cvmfs_dir} >/dev/null 2>&1 || true
done
voms-proxy-init -voms cms || true
export PYTHONUNBUFFERED=1
export ARCHITECTURE=${ARCHITECTURE}
export RELEASE_FORMAT=${RELEASE_FORMAT}
#Use previous WEEK for env if week day is Sunday(0)  or Monday(1) otherwise use current week
if [ $(date +%w) -lt 2 ] ; then
  IB_LAST_WEEK=$(ls -d /cvmfs/cms-ib.cern.ch/nweek-* | tail -2 | head -1)
else
  IB_LAST_WEEK=$(ls -d /cvmfs/cms-ib.cern.ch/nweek-* | tail -1)
fi
source \${IB_LAST_WEEK}/cmsset_default.sh  || true
scram -a ${ARCHITECTURE} project ${RELEASE_FORMAT}
cd ${RELEASE_FORMAT}
set +x
eval \$(scram runtime -sh)
set -x
export CMS_PATH=\${IB_LAST_WEEK}
if [ "${NO_IBEOS_UPDATES}" = "" ] ; then
  cp $WORKSPACE/cms-bot/das-utils/das_client $WORKSPACE/cms-bot/das-utils/das_client.py
  $WORKSPACE/cms-bot/das-utils/use-ibeos-sort
  export PATH=$WORKSPACE/cms-bot/das-utils:\$PATH
  which das_client
  grep 'ibeos-lfn-sort' \${LOCALRT}/src/Configuration/PyReleaseValidation/python/*.py || true
fi
EOF
