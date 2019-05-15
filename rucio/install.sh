#!/bin/bash -ex
RUCIO_CONFIG_URL="https://raw.githubusercontent.com/cms-sw/cmsdist/comp_gcc630/rucio-config.file"
INSTALL_DIR=$(/bin/pwd)
SET_CURRENT="no"
RUCIO_VERSION="latest"

while [ $# -gt 0 ]; do
  case $1 in
    -i|--install-dir )      INSTALL_DIR="$2"      ; shift; shift;;
    -c|--current )          SET_CURRENT="yes"     ;        shift;;
    -C|--rucio-config-url ) RUCIO_CONFIG_URL="$2" ; shift; shift;;
    -v|--rucio-version )    RUCIO_VERSION="$2"    ; shift; shift;;
    * ) echo "Error: Unknown arg '$1'"; exit 1;;
  esac
done

if [ ! -e ${INSTALL_DIR}/current ] ; then SET_CURRENT="yes" ; fi

if [ "${RUCIO_VERSION}" = "latest" ] ; then
  RUCIO_VERSION=$(pip search --disable-pip-version-check rucio-clients 2>&1 | grep '^rucio-clients ' | sed 's|).*||;s|.*(||')
fi

PIP_PKG=rucio-clients
export PYTHONUSERBASE="${INSTALL_DIR}/${RUCIO_VERSION}"
mkdir -p "${PYTHONUSERBASE}" "${INSTALL_DIR}/tmp"
export TMPDIR="${INSTALL_DIR}/tmp"
pip install --disable-pip-version-check --user ${PIP_PKG}==${RUCIO_VERSION}
rm -f ${INSTALL_DIR}/rucio.cfg
curl -s -o ${INSTALL_DIR}/rucio.cfg ${RUCIO_CONFIG_URL}
rm -f ${PYTHONUSERBASE}/etc/rucio.cfg
ln -s ../../rucio.cfg ${PYTHONUSERBASE}/etc/rucio.cfg
rm -rf ${TMPDIR}

cp -r $(dirname $0)/setup.sh ${INSTALL_DIR}/setup.sh
chmod 0644 ${INSTALL_DIR}/setup.sh
#touch ${PYTHONUSERBASE}/.cvmfscatalog

if [ "$SET_CURRENT" = "yes" ] ; then
  rm -f ${INSTALL_DIR}/current
  ln -s ${RUCIO_VERSION} ${INSTALL_DIR}/current
  /bin/bash ${INSTALL_DIR}/setup.sh
else
  /bin/bash ${INSTALL_DIR}/setup.sh ${RUCIO_VERSION}
fi

