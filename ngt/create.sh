#!/bin/bash -ex
function usage(){
  echo "ERROR: Usage $0 gpu-type session-id"
  echo "e.g."
  echo "  $0 mi300x 01"
  echo "  $0 h100 01"
  exit 1
}
THIS_DIR=$(dirname $0)
IMG_DATE="20260903"
GPU="$1"
ID="$2"
[ "$GPU" != "" ] || usage
[ "$ID" != "" ] || usage

if [ ! -f "${THIS_DIR}/${GPU}" ] ; then
  echo "ERROR: No such file ${THIS_DIR}/${GPU}"
  exit 1
fi
sed -e "s|@N@|$ID|;s|@IMG_DATE@|$IMG_DATE|" ${THIS_DIR}/${GPU} > session.yaml
kubectl --context ngt-token create -f session.yaml
