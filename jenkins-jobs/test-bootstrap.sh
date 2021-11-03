#!/bin/bash -ex
function get_logs() {
  mkdir -p upload/$1
  [ -e $1/tmp/bootstrap.log ] && cp $1/tmp/bootstrap.log upload/$1
  for l in $(find $1/BUILD/${ARCH} -maxdepth 4 -mindepth 4 -name log -type f | sed "s|$1/BUILD/${ARCH}/||") ; do
    d=$(dirname $l)
    mkdir -p upload/$1/$d
    mv $1/BUILD/${ARCH}/$l upload/$1/$d
  done
}

ARCH=$1
PKGTOOLS=$2
CMSDIST=$3
REPO="$4"
DISABLE_DEBUG="$5"
CMSSW_VERSION="$6"
GCC_PATH="$7"
BS_OPTS="--no-bootstrap"
if [ "${REPO}" = "" ] ; then
  REPO="test_boot_$ARCH"
  ssh -q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60 cmsbuild@cmsrep.cern.ch rm -rf /data/cmssw/repos/$REPO || true
else
  if ssh -q -o IdentitiesOnly=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ServerAliveInterval=60 cmsbuild@cmsrep.cern.ch test -L /data/cmssw/repos/$REPO/${ARCH}/latest ; then
    BS_OPTS=""
    GCC_PATH="NO_GCC_ENV"
  fi
fi

if [ -e "$HOME/bin/nproc" ] ; then export PATH="${HOME}/bin:${PATH}" ; fi
cmsBuild="./pkgtools/cmsBuild --repo $REPO -a $ARCH -j $(nproc)"

git clone --depth 1 https://github.com/cms-sw/cmsdist -b $CMSDIST
git clone --depth 1 https://github.com/cms-sw/pkgtools -b $PKGTOOLS

([ -f "${GCC_PATH}/etc/profile.d/init.sh" ] && source ${GCC_PATH}/etc/profile.d/init.sh ; $cmsBuild -i bootstrap ${BS_OPTS} build bootstrap-driver)
get_logs bootstrap
$cmsBuild -i bootstrap ${BS_OPTS} --sync-back upload bootstrap-driver
rm -rf bootstrap

if [ "${DISABLE_DEBUG}" = "true" ] ; then
  sed -i -e 's|^\s*%define\s\s*subpackageDebug\s|#subpackage debug disabled|' cmsdist/coral.spec cmsdist/cmssw.spec
fi
ERR=0
$cmsBuild -i toolconf --builder 3  build cmssw-tool-conf || ERR=1
get_logs toolconf
if [ $ERR -gt 0 ] ; then
  BLD_PKGS=$(ls toolconf/RPMS/${ARCH}/ | grep '.rpm$' | cut -d+ -f2 | grep -v 'coral-debug')
  if [ "X$BLD_PKGS" != "X" ] ; then $cmsBuild -i toolconf --builder 3  --sync-back upload ${BLD_PKGS} ; fi
  rm -rf toolconf
  exit 1
fi
$cmsBuild -i toolconf --builder 3 --sync-back upload cmssw-tool-conf
rm -rf toolconf

if [ "$CMSSW_VERSION" != "" ] ; then
  sed -i -e "s|^### RPM cms cmssw .*|### RPM cms cmssw $CMSSW_VERSION|"       cmsdist/cmssw.spec
  sed -i -e "s|^### RPM cms cmssw-ib .*|### RPM cms cmssw-ib $CMSSW_VERSION|" cmsdist/cmssw-ib.spec
  $cmsBuild -i release build cmssw-ib
  get_logs release
  $cmsBuild -i release --sync-back upload cmssw-ib
  rm -rf release
fi
