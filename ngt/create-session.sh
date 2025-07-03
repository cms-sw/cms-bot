#!/bin/bash
function usage() {
  echo "$1"
  echo "$0 options"
  echo "   -t|--type <amd|nvidia>   Type of GPU e.g. amd or nvidia. Default is nvidia"
  echo "   -c|--count <num>         Number of GPUs e.g. 1. Default is 1"
  echo "   -g|--gpu   <name>        GPU name. Default is NVIDIA-H100-NVL"
  echo $2
}

THISDIR=$(dirname $0)
export GPU_TYPE="nvidia"
export GPU_COUNT="1"
export GPU="NVIDIA-H100-NVL"
export SESSION_ID=$(date +%Y%M%d%H%m)

while [[ $# -gt 0 ]]; do
  case ${1} in
    -h|--help) usage "" 0;;
	  -t|--type)  export GPU_TYPE=$2; shift; shift ;;
	  -c|--count) export GPU_COUNT=$2; shift; shift;;
	  -g|--gpu)   export GPU=$2; shift; shift;;
    * ) usage "ERROR: Unknown command line option \"$1\"." 1 ;;
  esac
done
if [ "${GPU_TYPE}" = "" ] || [ "${GPU_COUNT}" = "" ] || [ "${GPU}" = "" ] ; then
  usage "Error: Missing option" 1
fi

sed -e "s|@GPU@|${GPU}|;s|@GPU_TYPE@|${GPU_TYPE}|;s|@GPU_COUNT@|${GPU_COUNT}|;s|@SESSION_ID@|${SESSION_ID}|" ${THISDIR}/ngt-session.yaml 
