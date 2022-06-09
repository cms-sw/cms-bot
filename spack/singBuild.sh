#!/bin/bash -x
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export USE_SINGULARITY=true
export WORKDIR=$WORKSPACE
#if [ ! -z ${SPACK_GPG_KEY} ]; then
#  SPACK_GPG_KEY_DIR=$(dirname ${SPACK_GPG_KEY})
#  export MOUNT_DIRS="${SPACK_GPG_KEY_DIR}:${SPACK_GPG_KEY_DIR}"
#fi

rm -f ${WORKSPACE}/fail

cd $WORKSPACE/cms-bot
./spack/bootstrap.sh

${WORKSPACE}/docker_launcher.sh ./spack/build.sh
if [ -e ${WORKSPACE}/fail ]; then
    echo Build falied, uploading monitor data
    tar -zcf $WORKSPACE/monitor.tar.gz $WORKSPACE/monitor
    scp $WORKSPACE/monitor.tar.gz cmsbuild@lxplus:/eos/user/r/razumov/www/CMS/mirror
    rm $WORKSPACE/monitor.tar.gz
    touch $WORKSPACE/fail
    exit 1
fi
#echo Upload monitor data
#if [ ! -z ${SPACKMON_TOKEN} ]; then retry 5 bin/spack monitor --monitor-host http://cms-spackmon.cern.ch/cms-spackmon --monitor-keep-going --monitor-tags ${SPACK_ENV_NAME} upload $WORKSPACE/monitor; fi;
if [ ${UPLOAD_BUILDCACHE-x} = "true" ]; then
  echo Prepare mirror and buildcache
  bin/spack -e ${SPACK_ENV_NAME} mirror create -d $WORKSPACE/mirror --all --dependencies
  bin/spack -e ${SPACK_ENV_NAME} buildcache create -r -f -a -d $WORKSPACE/mirror
  bin/spack -e ${SPACK_ENV_NAME} gpg publish -d $WORKSPACE/mirror --rebuild-index
  cd $WORKSPACE
  echo Upload mirror
  rsync -e "ssh -o StrictHostKeyChecking=no -o GSSAPIAuthentication=yes -o GSSAPIDelegateCredentials=yes" --recursive --links --ignore-times --ignore-existing $WORKSPACE/mirror cmsbuild@lxplus:/eos/user/r/razumov/www/CMS/
fi
echo All done
