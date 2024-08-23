#!/bin/bash -e
UPSTREAM_SPACK=${UPSTREAM_SPACK:-"/home/razumov/Work/_CMS/vanilla_spack"}
#########################################################################################################################
[ -d ${UPSTREAM_SPACK} ] || (echo "Invalid upstream Spack location: ${UPSTREAM_SPACK}"; exit 2)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd $(dirname $SCRIPT_DIR)
[ $# -lt 1 ] && (echo "Usage: backport.sh <package> [<package> ...]"; exit 1)
for pname in "$@"
do
    updir=${UPSTREAM_SPACK}/var/spack/repos/builtin/packages/${pname}
    [ ! -d ${updir} -o ! -f ${updir}/package.py ] && (echo "Can't find recipe for $pname"; exit 2)
    cp -rf ${updir} repos/backport/packages
    cp -rf repos/backport/packages/${pname} spack/var/spack/repos/builtin/packages
done
