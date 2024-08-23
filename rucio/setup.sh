
SELECTED_VERSION=${1-current}
ARCH=$(uname -m)/$(/cvmfs/cms.cern.ch/common/cmsos | cut -d_ -f1 | sed 's|^[a-z]*|rhel|')
THISDIR=$(cd $(dirname ${BASH_SOURCE:-${(%):-%N}}) >/dev/null 2>&1; /bin/pwd)/${ARCH}/
if [ ! -e ${THISDIR}/${SELECTED_VERSION}/bin/rucio ] ; then
  echo "Error: Unable to find rucio version '${SELECTED_VERSION}'" >&2
  return
fi
PYTHON_DIR="$(grep '#!/' ${THISDIR}/${SELECTED_VERSION}/bin/rucio | sed 's|^#!||;s|/bin/python[^/]*$||')"
if [ -e "${PYTHON_DIR}/etc/profile.d/init.sh" ] ; then
  source "${PYTHON_DIR}/etc/profile.d/init.sh"
fi
PY_PATH=$(ls -d --color=never ${THISDIR}/${SELECTED_VERSION}/lib/python*/site-packages)
export PATH=${THISDIR}/${SELECTED_VERSION}/bin${PATH:+:$PATH}
export PYTHONPATH=${PY_PATH}${PYTHONPATH:+:$PYTHONPATH}
export RUCIO_HOME=${THISDIR}/${SELECTED_VERSION}
rucio --version
