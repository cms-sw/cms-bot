#!/bin/bash -ex
vm=$(grep '^vm=' $1 | sed 's|^vm=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_-]*$' || true)
pj=$(grep '^pj=' $1 | sed 's|^pj=||' | grep -E '^(CMS_SDT_Build|CMS_SDT_CI|CMS_Miscellaneous_ARM)$' || true)
[ "$pj" != "" ] || pj="$vm"
if [ "${vm}" = "" ] ; then
  echo "ERROR: Wrong VM name"
  exit 1
fi
ERR=0
source $(dirname $0)/setup-env.sh "${pj}"
ai-kill ${vm} || ERR=1
ai-foreman delhost --do-not-ask ${vm} || true
exit $ERR
