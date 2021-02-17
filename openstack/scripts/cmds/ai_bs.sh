#!/bin/bash -e
vm=$(grep '^vm=' $1 | sed 's|^vm=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$' || true)
hg=$(grep '^hg=' $1 | sed 's|^hg=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$' || true)
if [ "${vm}" = "" ] ; then
  echo "ERROR: Wrong VM name"
  exit 1
fi
ERR=0
source $(dirname $0)/setup-env.sh
ai-kill ${vm} || ERR=1
ai-foreman delhost ${vm} || true
exit $ERR
