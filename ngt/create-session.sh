#!/bin/bash
function usage() {
  [ "$1" = "" ] || echo "$1"
  echo "$0 options"
  echo "   -g|--gpu   <amd|nvidia>  Type of GPU. Default is nvidia"
  echo "                            Value values are"
  for g in $(echo ${VALID_GPUS} | tr ' ' '\n' | sed 's|:.*||') ; do
    echo "                            - $g"
  done
  echo "   -n|--name  <gpu-name>    Name of GPU. Default is $(echo ${VALID_GPUS} | tr ' ' '\n' | sed 's|nvidia:||' | sed 's|.*:||' | tr ',' '\n' | head -1)"
  echo "                            Valid values are:"
  for g in $(echo ${VALID_GPUS} | tr ' ' '\n' | sed 's|:.*||') ; do
    echo "                            $g:"
    for n in $(echo ${VALID_GPUS} | tr ' ' '\n' | grep "^${g}:" | sed 's|.*:||' | tr ',' '\n') ; do
      echo "                              - $n"
    done
  done 
  echo "   -c|--count <num>         Number of GPUs e.g. 1. Default is 1"
  echo "   -h|--help                Print this help message"
  echo ""
  echo "Create: kubectl create -f session.yaml"
  echo "List:   kubectl get po"
  echo "Delete: kubectl delete po <session-id>"
  echo "Connect: ssh <session-id>@ngt.cern.ch"
  exit $2
}

#Supported/available GPUS
#Format: gpu:<comma-separated-list-of-gpus> gpu:<comma-separated-list-of-gpus> ..."
VALID_GPUS="amd:AMD_Instinct_MI300X_OAM nvidia:NVIDIA-H100-NVL,NVIDIA-L40S"
VALID_PRODUCTS="amd:product-name nvidia:product"

THISDIR=$(dirname $0)
GPU_TYPE="nvidia"
GPU_COUNT="1"
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
PRODUCT=$(echo ${VALID_PRODUCTS} | tr ' ' '\n' | grep "${GPU_TYPE}:" | sed 's|.*:||')
SESSION_ID=$(echo ${GPU} | tr 'A-Z-' 'a-z_')-$(date +%Y%M%d%H%m)
sed -e "s|@PRODUCT@|${PRODUCT}|;s|@GPU@|${GPU}|;s|@GPU_TYPE@|${GPU_TYPE}|;s|@GPU_COUNT@|${GPU_COUNT}|;s|@SESSION_ID@|${SESSION_ID}|" ${THISDIR}/ngt-session.yaml
