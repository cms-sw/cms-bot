#!/bin/bash -ex
vm=$(head -1 $1 | grep '^vm=' | sed 's|^vm=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$' || true)
if [ "${vm}" = "" ] ; then
  echo "ERROR: Wrong VM name"
  exit 1
fi
ERR=0
source $(dirname $0)/setup-env.sh $vm
ai-kill ${vm} || ERR=1
ai-foreman delhost --do-not-ask ${vm} || true
exit $ERR
