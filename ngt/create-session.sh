#!/bin/bash
function usage() {
  [ "$1" = "" ] || echo "$1"
  echo "$0 options"
  echo "   -g|--gpu   <amd|nvidia>  Type of GPU e.g. amd or nvidia. Default is nvidia"
  echo "   -n|--name  <gpu-name>    Name of GPU e.g. NVIDIA-H100-NVL"
  echo "   -c|--count <num>         Number of GPUs e.g. 1. Default is 1"
  echo "   -h|--help                Print this help message"
  exit $2
}

#Supported/available GPUS
#Format: gpu:<comma-separated-list-of-gpus> gpu:<comma-separated-list-of-gpus> ..."
VALID_GPUS="amd:AMD_Instinct_MI300X_OAM nvidia:NVIDIA-H100-NVL"

THISDIR=$(dirname $0)
export GPU_TYPE="nvidia"
export GPU_COUNT="1"
GPU_NAME=""

while [[ $# -gt 0 ]]; do
  case ${1} in
    -h|--help) usage "" 0;;
	  -c|--count) export GPU_COUNT=$2; shift; shift;;
	  -g|--gpu)   export GPU_TYPE=$2; shift; shift;;
    -n|--name)  GPU_NAME=$2; shift; shift;;
    * ) usage "ERROR: Unknown command line option \"$1\"." 1 ;;
  esac
done
GPU=$(echo ${VALID_GPUS} | tr ' ' '\n' | grep "^${GPU_TYPE}:" | sed 's|.*:||')
if [ "${GPU_NAME}" != "" ] ; then
  GPU=$(echo $GPU | tr ',' '\n' | grep "^${GPU_NAME}" | head -1)
else
  GPU=$(echo $GPU | tr ',' '\n' | head -1)
fi
if [ "${GPU_TYPE}" = "" ] || [ "${GPU_COUNT}" = "" ] || [ "${GPU}" = "" ] ; then
  usage "Error: Missing option" 1
fi
export SESSION_ID=$(date +%Y%M%d%H%m)
sed -e "s|@GPU@|${GPU}|;s|@GPU_TYPE@|${GPU_TYPE}|;s|@GPU_COUNT@|${GPU_COUNT}|;s|@SESSION_ID@|${SESSION_ID}|" ${THISDIR}/ngt-session.yaml
