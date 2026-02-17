#!/bin/bash -ex
function usage(){
  echo "ERROR: Usage $0 gpu-type session-id"
  echo "e.g."
  echo "  $0 mi300x 01"
  echo "  $0 h100 01"
  exit 1
}

GPU="$1"
ID="$2"
[ "$GPU" != "" ] || usage
[ "$ID" != "" ] || usage
if [ ! -f "${GPU}" ] ; then
  echo "ERROR: No such file $GPU"
  exit 1
fi
sed -e "s|@N@|$ID|" $GPU > session.yaml
kubectl create -f session.yaml
