#!/bin/bash -ex
pj=$(grep '^pj=' $1 | sed 's|^pj=||' | grep -E '^(CMS_SDT_Build|CMS_SDT_CI|CMS_Miscellaneous_ARM)$' || true)
hg=$(grep '^hg=' $1 | sed 's|^hg=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_/-]*$' || true)
opts=$(grep '^opts=' $1 | sed 's|^opts=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_=. -]*$' || true)
if [ "${hg}" = "" ] ; then
  echo "ERROR: Missing hostgroup"
  exit 1
fi
if [ "$pj" = "" ] ; then pj="CMS_SDT_Build" ; fi
source $(dirname $0)/setup-env.sh ${pj}
ai-bs -g ${hg} ${opts}
