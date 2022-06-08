#!/bin/bash
### ENV ###
# if [ -z ${RPM_INSTALL_PREFIX+x} ]; then export RPM_INSTALL_PREFIX=/cvmfs/cms-ib.cern.ch/spack; fi
if [[ "${RPM_INSTALL_PREFIX}" != /* ]]; then RPM_INSTALL_PREFIX=${WORKSPACE}/${RPM_INSTALL_PREFIX}; fi

if [ "$(uname)" == "Darwin" ]; then
	CORES=$(sysctl -n hw.ncpu)
elif [ "$(uname)" == "Linux" ]; then
	CORES=$(awk '/^processor/ { N++} END { print N }' /proc/cpuinfo)
fi
export CORES
echo Setup Spack for CMS
cd "$WORKSPACE"/cms-spack-repo
bash -xe ./bootstrap.sh || (echo "Boostrap failed"; exit 1)
cd spack
echo Forcing bootstrap
bin/spack -d solve zlib
export SPACK_DISABLE_LOCAL_CONFIG=true
export SPACK_USER_CACHE_PATH=$WORKSPACE
# source share/spack/setup-env.sh
echo Add signing key
bin/spack buildcache keys --force --install --trust
echo Set install root
bin/spack config add "config:install_tree:root:${RPM_INSTALL_PREFIX}"
echo Start the installation
mkdir -p "${RPM_INSTALL_PREFIX}"
#spack env activate ${SPACK_ENV_NAME}
bin/spack -e "${SPACK_ENV_NAME}" install -j"$CORES" --fail-fast --cache-only --require-full-hash-match
if [$? -eq 0 ]; then
    echo Installation complete
else
    echo "ERROR: Installation failed"
    touch $WORKSPACE/fail
fi
