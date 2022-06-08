#!/bin/bash
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE

cd $WORKSPACE/cms-bot
./spack/bootstrap.sh
# Inject necessary environment variables into install.sh script
sed -ie "s@### ENV ###@export RPM_INSTALL_PREFIX=${RPM_INSTALL_PREFIX}\nexport WORKSPACE=${WORKSPACE}\nexport SPACK_ENV_NAME=${SPACK_ENV_NAME}@"

source ${WORKSPACE}/cms-bot/dockerrun.sh ; dockerrun ./spack/build.sh
[ -e ${WORKSPACE}/fail ] && exit 1
