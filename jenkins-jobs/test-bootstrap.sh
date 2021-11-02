#!/bin/bash -ex
ARCH=$1
CMSSW_VERSION=$2
PKGTOOLS=$3
CMSDIST=$4
if [ -f "${5}/etc/profile.d/init.sh" ] ; then source ${5}/etc/profile.d/init.sh ; fi
repo="boot_$(date +%Y%m%d)_$ARCH"
cmsBuild="./pkgtools/cmsBuild --repo $repo -a $ARCH -j $(nproc)"

git clone --depth 1 https://github.com/cms-sw/cmsdist -b $CMSDIST
git clone --depth 1 https://github.com/cms-sw/pkgtools -b $PKGTOOLS
sed -i -e 's|^\s*%define\s\s*subpackageDebug\s|#subpackage debug disabled|' cmsdist/coral.spec cmsdist/cmssw.spec
sed -i -e "s|^### RPM cms cmssw .*|### RPM cms cmssw $CMSSW_VERSION|"       cmsdist/cmssw.spec
sed -i -e "s|^### RPM cms cmssw-ib .*|### RPM cms cmssw-ib $CMSSW_VERSION|" cmsdist/cmssw-ib.spec

$cmsBuild -i bootstrap --no-bootstrap build bootstrap-driver
$cmsBuild -i bootstrap --no-bootstrap --sync-back upload bootstrap-driver
rm -rf bootstrap

perl -p -i -e 's/^[\s]*%define[\s]+subpackageDebug[\s]+./#subpackage debug disabled/' cmsdist/coral.spec cmsdist/cmssw.spec
$cmsBuild -i toolconf --builder 3 upload cmssw-tool-conf
rm -rf toolconf

$cmsBuild -i release build cmssw-ib
$cmsBuild -i release upload cmssw-ib
rm -rf release
