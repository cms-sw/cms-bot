#!/bin/bash -x
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export CVMFS_REPOSITORY=cms-ib.cern.ch
export BASEDIR=/cvmfs/$CVMFS_REPOSITORY
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE

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
[ -e ${WORKSPACE}/fail ] && ./cvmfs_deployment/abort_transaction.sh || ./cvmfs_deployment/publish_transaction.sh
