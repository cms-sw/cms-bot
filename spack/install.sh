#!/bin/bash -x
# For boto3
export PYTHONPATH=/cvmfs/cms-ib.cern.ch/share/python3/lib/python3.6/site-packages:$PYTHONPATH
export PYTHONUNBUFFERED=1
export S3_ENDPOINT_URL=https://s3.cern.ch

if [[ "${RPM_INSTALL_PREFIX}" != /* ]]; then RPM_INSTALL_PREFIX=${WORKSPACE}/${RPM_INSTALL_PREFIX}; fi

if [ "$(uname)" == "Darwin" ]; then
	CORES=$(sysctl -n hw.ncpu)
elif [ "$(uname)" == "Linux" ]; then
	CORES=$(awk '/^processor/ { N++} END { print N }' /proc/cpuinfo)
fi
export CORES
cd ${WORKSPACE}/spack
export SPACK_DISABLE_LOCAL_CONFIG=true
export SPACK_USER_CACHE_PATH=$WORKSPACE
source share/spack/setup-env.sh
echo Add signing key
spack buildcache keys --force --install --trust
# echo Set install root
# spack config add 'config:install_tree:projections:all:${ARCHITECTURE}/${COMPILERNAME}-${COMPILERVER}/${PACKAGE}/${VERSION}-${HASH}'
spack config add "config:install_tree:root:${RPM_INSTALL_PREFIX}"
echo Force bootstrap
spack -d solve zlib || exit 1
echo Get patchelf
GCC_VER=$(gcc --version | head -1 | cut -d ' ' -f 3)
spack compiler find --scope=site
spack install --reuse --cache-only patchelf%gcc@${GCC_VER} || exit 1
spack load patchelf%gcc@${GCC_VER}
echo Start the installation
mkdir -p "${RPM_INSTALL_PREFIX}"
spack env activate ${SPACK_ENV_NAME}
spack -e "${SPACK_ENV_NAME}" install -j"$CORES" --fail-fast --cache-only --require-full-hash-match
exit_code=$?
if [ ${exit_code} -eq 0 ]; then
    echo Installation complete
else
    echo "ERROR: Installation failed"
    touch $WORKSPACE/fail
fi
exit ${exit_code}
