#!/bin/bash -x
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export SCRAM_ARCH=$CMSARCH
export CVMFS_REPOSITORY=cms-ib.cern.ch
export BASEDIR=/cvmfs/$CVMFS_REPOSITORY
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE

weekno=$(tail -1 $WORKSPACE/cms-bot/ib-weeks)
export RPM_INSTALL_PREFIX=$BASEDIR/$weekno/spack

rm -f ${WORKSPACE}/fail

cd $WORKSPACE/cms-bot
./spack/bootstrap.sh
./cvmfs_deployment/start_transaction.sh

# Check if the transaction really happened
if [ `touch $BASEDIR/is_writable 2> /dev/null; echo "$?"` -eq 0 ]; then
  rm $BASEDIR/is_writable
else
  echo CVMFS filesystem is not writable. Aborting.
  echo " " | mail -s "$CVMFS_REPOSITORY cannot be set to transaction" cms-sdt-logs@cern.ch
  exit 1
fi

# Use dockerrun since we may need to use qemu
source ${WORKSPACE}/cms-bot/dockerrun.sh ; dockerrun ${WORKSPACE}/cms-bot/spack/install.sh
exit_code=$?
[ -e ${WORKSPACE}/fail -o ${exit_code} -ne 0 ] && ./cvmfs_deployment/abort_transaction.sh || 
${WORKSPACE}/cms-bot/cvmfs/cms-ib.cern.ch/cvmfsdirtab.sh
./cvmfs_deployment/publish_transaction.sh
exit ${exit_code}
