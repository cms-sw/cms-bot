#!/bin/bash -ex
vm=$(grep '^vm=' $1 | sed 's|^vm=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$' || true)
pj=$(grep '^pj=' $1 | sed 's|^pj=||' | grep '^[A-Z][A-Z_]*$' || echo $vm)
if [ "${vm}" = "" ] ; then
  echo "ERROR: Wrong VM name"
  exit 1
fi
ERR=0
source $(dirname $0)/setup-env.sh "${pj}"
ai-kill ${vm} || ERR=1
ai-foreman delhost --do-not-ask ${vm} || true
exit $ERR
