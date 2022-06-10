#!/bin/bash -x
# For boto3
export PYTHONPATH=/cvmfs/cms-ib.cern.ch/share/python3/lib/python3.6/site-packages:$PYTHONPATH
export S3_ENDPOINT_URL=https://s3.cern.ch

if [[ "${RPM_INSTALL_PREFIX}" != /* ]]; then RPM_INSTALL_PREFIX=${WORKSPACE}/${RPM_INSTALL_PREFIX}; fi

if [ "$(uname)" == "Darwin" ]; then
	CORES=$(sysctl -n hw.ncpu)
elif [ "$(uname)" == "Linux" ]; then
	CORES=$(awk '/^processor/ { N++} END { print N }' /proc/cpuinfo)
fi
export CORES
cd ${WORKSPACE}/spack
ls
export SPACK_DISABLE_LOCAL_CONFIG=true
export SPACK_USER_CACHE_PATH=$WORKSPACE
echo Forcing bootstrap
bin/spack -d solve zlib || exit 1
echo Getting patchelf
bin/spack install --reuse --cache-only patchelf || exit 1
# source share/spack/setup-env.sh
echo Add signing key
bin/spack buildcache keys --force --install --trust
echo Set install root
bin/spack config add "config:install_tree:root:${RPM_INSTALL_PREFIX}"
echo Start the installation
mkdir -p "${RPM_INSTALL_PREFIX}"
#spack env activate ${SPACK_ENV_NAME}
bin/spack -e "${SPACK_ENV_NAME}" install -j"$CORES" --fail-fast --cache-only --require-full-hash-match
if [ $? -eq 0 ]; then
    echo Installation complete
else
    echo "ERROR: Installation failed"
    touch $WORKSPACE/fail
fi
