#!/bin/bash
cat <<EOF
#!/bin/bash -ex
klist || true
kinit -R || true
hostname
cvmfs_config probe || true
for cvmfs_dir in cms-ci.cern.ch  \$(grep CVMFS_REPOSITORIES= /etc/cvmfs/default.local | sed "s|.*=||;s|'||g" | sed 's|"||g' | tr ',' '\n'  | grep cern.ch) ; do
  ls -l /cvmfs/\${cvmfs_dir} >/dev/null 2>&1 || true
done
voms-proxy-init -voms cms || true
export PYTHONUNBUFFERED=1
export ARCHITECTURE=${ARCHITECTURE}
export SCRAM_ARCH=${ARCHITECTURE}
export RELEASE_FORMAT=${RELEASE_FORMAT}
export SCRAM_PREFIX_PATH=$WORKSPACE/cms-bot/das-utils
export LC_ALL=C
UNAME=$(echo ${ARCHITECTURE} | cut -d_ -f2)
[ "\${UNAME}" != "amd64" ] || UNAME="x86_64"
#Use previous WEEK for env if week day is Sunday(0)  or Monday(1) otherwise use current week
if [ $(date +%w) -lt 2 ] ; then
  IB_LAST_WEEK=\$(ls -d /cvmfs/cms-ib.cern.ch/sw/\${UNAME}/nweek-* | tail -2 | head -1)
else
  IB_LAST_WEEK=\$(ls -d /cvmfs/cms-ib.cern.ch/sw/\${UNAME}/nweek-* | tail -1)
fi
source \${IB_LAST_WEEK}/cmsset_default.sh  || true
scram -a ${ARCHITECTURE} project ${RELEASE_FORMAT}
cd ${RELEASE_FORMAT}
if [ -f config/SCRAM/linkexternal.py ] ; then
  sed -i -e 's|%s build|echo %s build|'  config/SCRAM/linkexternal.py || true
fi
set +x
#Check for syste commands to override e.g. ps hangs in ASAN env
case ${RELEASE_FORMAT} in
  *_ASAN_* )
   $CMS_BOT_DIR/system-overrides.sh $WORKSPACE/system-overrides
   export SCRAM_PREFIX_PATH=$WORKSPACE/system-overrides:${SCRAM_PREFIX_PATH}
   ;;
esac
eval \$(scram runtime -sh)
echo "PATH"
echo \$PATH | tr ':' '\n'
echo "LD_LIBRARY_PATH"
echo \$LD_LIBRARY_PATH | tr ':' '\n'
set -x
export CMS_PATH="/cvmfs/cms-ib.cern.ch"
export SITECONFIG_PATH="/cvmfs/cms-ib.cern.ch/SITECONF/local"
export CMSBOT_PYTHON_CMD=\$(which python3 >/dev/null 2>&1 && echo python3 || echo python)
if [ "${NO_IBEOS_UPDATES}" = "" ] ; then
  cp $WORKSPACE/cms-bot/das-utils/das_client $WORKSPACE/cms-bot/das-utils/das_client.py
  $WORKSPACE/cms-bot/das-utils/use-ibeos-sort
  export PATH=$WORKSPACE/cms-bot/das-utils:\$PATH
  which dasgoclient
  grep 'ibeos-lfn-sort' \${LOCALRT}/src/Configuration/PyReleaseValidation/python/*.py || true
fi
EOF
