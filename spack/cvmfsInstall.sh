#!/bin/bash
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export CVMFS_REPOSITORY=cms-ib.cern.ch
export BASEDIR=/cvmfs/$CVMFS_REPOSITORY
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE

cd $WORKSPACE/cms-bot
./spack/bootstrap.sh
# Inject necessary environment variables into install.sh script
sed -ie "s@### ENV ###@export RPM_INSTALL_PREFIX=${RPM_INSTALL_PREFIX}\nexport WORKSPACE=${WORKSPACE}\nexport SPACK_ENV_NAME=${SPACK_ENV_NAME}@"

./cvmfs_deployment/start_transaction.sh

# Check if the transaction really happened
if [ `touch $BASEDIR/is_writable 2> /dev/null; echo "$?"` -eq 0 ]; then
  rm $BASEDIR/is_writable
else
  echo CVMFS filesystem is not writable. Aborting.
  echo " " | mail -s "$CVMFS_REPOSITORY cannot be set to transaction" cms-sdt-logs@cern.ch
  exit 1
fi

source ${WORKSPACE}/cms-bot/dockerrun.sh ; dockerrun ./spack/install.sh
[ -e ${WORKSPACE}/fail ] && ./cvmfs_deployment/abort_transaction.sh || ./cvmfs_deployment/publish_transaction.sh
