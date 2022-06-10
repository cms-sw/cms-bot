#!/bin/bash -x
export CMSARCH=${CMSARCH:-slc7_amd64_gcc900}
export SCRAM_ARCH=$CMSARCH
export USE_SINGULARITY=true
export WORKDIR=${WORKSPACE}
if [ x$DOCKER_IMG == "x" ]; then
    arch="$(echo $CMSARCH | cut -d_ -f2)"
    os=$(echo $CMSARCH | cut -d_ -f1 | sed 's|slc7|cc7|')
    if [ "${os}" = "rhel8" ] ; then os="ubi8" ; fi
    DOCKER_IMG="cmssw/${os}:${arch}"
    if [ "${arch}" = "amd64" ] ; then
      DOCKER_IMG="cmssw/${os}:x86_64"
    fi
fi
export DOCKER_IMG

rm -f ${WORKSPACE}/fail

${WORKSPACE}/cms-bot/spack/bootstrap.sh

${WORKSPACE}/cms-bot/docker_launcher.sh ${WORKSPACE}/cms-bot/spack/build.sh
if [ -e ${WORKSPACE}/fail ]; then
    echo Build falied, uploading monitor data
    tar -zcf ${WORKSPACE}/monitor.tar.gz ${WORKSPACE}/monitor
    scp ${WORKSPACE}/monitor.tar.gz cmsbuild@lxplus:/eos/user/r/razumov/www/CMS/mirror
    rm ${WORKSPACE}/monitor.tar.gz
    touch ${WORKSPACE}/fail
    exit 1
fi
#echo Upload monitor data
#if [ ! -z ${SPACKMON_TOKEN} ]; then retry 5 bin/spack monitor --monitor-host http://cms-spackmon.cern.ch/cms-spackmon --monitor-keep-going --monitor-tags ${SPACK_ENV_NAME} upload ${WORKSPACE}/monitor; fi;
if [ ${UPLOAD_BUILDCACHE-x} = "true" ]; then
  echo Prepare mirror and buildcache
  cd ${WORKSPACE}/spack
  bin/spack -e ${SPACK_ENV_NAME} mirror create -d ${WORKSPACE}/mirror --all --dependencies
  bin/spack -e ${SPACK_ENV_NAME} buildcache create -r -f -a -d ${WORKSPACE}/mirror
  bin/spack -e ${SPACK_ENV_NAME} gpg publish -d ${WORKSPACE}/mirror --rebuild-index
  cd ${WORKSPACE}
  echo Upload mirror
  rsync -e "ssh -o StrictHostKeyChecking=no -o GSSAPIAuthentication=yes -o GSSAPIDelegateCredentials=yes" --recursive --links --ignore-times --ignore-existing ${WORKSPACE}/mirror cmsbuild@lxplus:/eos/user/r/razumov/www/CMS/
fi
echo All done
