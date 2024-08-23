#!/bin/bash -ex
export EOS_MGM_URL="root://eoscms.cern.ch"
eos_cmd="/usr/bin/eos"
eos_base="/store/user/cmsbuild"
xrd_eos_base="root://eoscms.cern.ch//eos/cms"
lfn=$1
redirector=$2
force=$3

if [ "$redirector" = "" ] ; then redirector="root://cms-xrd-global.cern.ch"; fi
eos_file="${eos_base}${lfn}"
if [ "$force" != "true" ] ; then
  if ${eos_cmd} stat -f ${eos_file} >/dev/null 2>&1 ; then
    echo "Already exists: ${lfn}"
    exit 0
  fi
fi
eos_dir=$(dirname ${eos_base}/${lfn})
${eos_cmd} mkdir -p ${eos_dir}
ERR=0
for rd in ${redirector} $(echo ${redirector} root://cms-xrd-global.cern.ch root://cmsxrootd.fnal.gov root://eoscms.cern.ch root://xrootd-cms.infn.it | tr ' ' '\n' | sort | uniq | grep 'root:' | grep -v "^${redirector}") ; do
  ERR=0
  xrdcp --force --posc -v ${rd}/${lfn} "${xrd_eos_base}/${eos_file}?eos.atomic=1" || ERR=1
  if [ $ERR -eq 0 ] ; then break ; fi
done
if [ $ERR -gt 0 ] ; then exit $ERR ; fi
${eos_cmd} stat -f ${eos_file}
echo ALL_OK
