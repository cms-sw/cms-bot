#!/bin/bash -ex
PYTHON_DIR="/cvmfs/cms.cern.ch/slc7_amd64_gcc700/external/py2-pip/9.0.3-pafccj"
RUCIO_CONFIG_URL="https://raw.githubusercontent.com/cms-sw/cmsdist/comp_gcc630/rucio-config.file"
INSTALL_DIR=$(/bin/pwd)
SET_CURRENT="no"
RUCIO_VERSION="latest"

while [ $# -gt 0 ]; do
  case $1 in
    -i|--install-dir )      INSTALL_DIR="$2"      ; shift; shift;;
    -c|--current )          SET_CURRENT="yes"     ;        shift;;
    -C|--rucio-config-url ) RUCIO_CONFIG_URL="$2" ; shift; shift;;
    -p|--python )           PYTHON_DIR="$2"       ; shift; shift;;
    -v|--rucio-version )    RUCIO_VERSION="$2"    ; shift; shift;;
  esac
done

set +x ; source ${PYTHON_DIR}/etc/profile.d/init.sh ;set -x

if [ "${RUCIO_VERSION}" = "latest" ] ; then
  RUCIO_VERSION=$(pip search rucio-clients 2>&1 | grep '^rucio-clients ' | sed 's|).*||;s|.*(||')
fi

PIP_PKG=rucio-clients
export PYTHONUSERBASE="${INSTALL_DIR}/${RUCIO_VERSION}"
mkdir -p "${PYTHONUSERBASE}" "${INSTALL_DIR}/tmp"
export TMPDIR="${INSTALL_DIR}/tmp"
pip install --user ${PIP_PKG}
rm -f ${INSTALL_DIR}/rucio.cfg
curl -s -o ${INSTALL_DIR}/rucio.cfg ${RUCIO_CONFIG_URL}
rm -f ${PYTHONUSERBASE}/etc/rucio.cfg
ln -s ../../rucio.cfg ${PYTHONUSERBASE}/etc/rucio.cfg
rm -rf ${TMPDIR}

cp -r $(dirname $0)/setup.sh ${INSTALL_DIR}/setup.sh
chmod 0644 ${INSTALL_DIR}/setup.sh

if [ "$SET_CURRENT" = "yes" ] ; then
  rm -f ${INSTALL_DIR}/current
  ln -s ${RUCIO_VERSION} ${INSTALL_DIR}/current
  /bin/bash ${INSTALL_DIR}/setup.sh
else
  /bin/bash ${INSTALL_DIR}/setup.sh ${RUCIO_VERSION}
fi

