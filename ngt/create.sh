#!/bin/bash -ex
function usage(){
  echo "ERROR: Usage $0 gpu-type session-id"
  echo "e.g."
  echo "  $0 mi300x 01"
  echo "  $0 h100 01"
  exit 1
}

IMG_DATE="20260903"
GPU="$1"
ID="$2"
[ "$GPU" != "" ] || usage
[ "$ID" != "" ] || usage
if [ ! -f "${GPU}" ] ; then
  echo "ERROR: No such file $GPU"
  exit 1
fi
sed -e "s|@N@|$ID|;s|@IMG_DATE@|$IMG_DATE|" $GPU > session.yaml
kubectl --context ngt-token create -f session.yaml
