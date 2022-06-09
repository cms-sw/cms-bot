#!/bin/bash
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE
if [ ! -z ${SPACK_GPG_KEY} ]; then
  SPACK_GPG_KEY_DIR=$(dirname ${SPACK_GPG_KEY})
  export MOUNT_DIRS="${SPACK_GPG_KEY_DIR}:${SPACK_GPG_KEY_DIR}"
fi

rm -f ${WORKSPACE}/fail

cd $WORKSPACE/cms-bot
./spack/bootstrap.sh

source ${WORKSPACE}/cms-bot/dockerrun.sh ; dockerrun ./spack/build.sh
[ -e ${WORKSPACE}/fail ] && exit 1
