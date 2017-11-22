#!/bin/bash -ex
export EOS_MGM_URL="root://eoscms.cern.ch"
eos_cmd="/usr/bin/eos"
eos_base="/store/user/cmsbuild"
xrd_eos_base="root://eoscms.cern.ch//eos/cms"
lfn=$1
redirector=$2

if [ "$redirector" = "" ] ; then redirector="root://cms-xrd-global.cern.ch"; fi
eos_file="${eos_base}${lfn}"
eos_dir=$(dirname ${eos_base}/${lfn})
${eos_cmd} mkdir -p ${eos_dir}
${eos_cmd} rm ${eos_file}.tmp >/dev/null 2>&1 || true
xrdcp --force --posc -v ${redirector}/${lfn} "${xrd_eos_base}/${eos_file}?eos.atomic=1"
${eos_cmd} stat -f ${eos_file}
echo ALL_OK
