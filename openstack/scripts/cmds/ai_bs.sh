#!/bin/bash -ex
hg=$(grep '^hg=' $1 | sed 's|^hg=||' | grep '^[a-zA-Z0-9_-][a-zA-Z0-9_/-]*$' || true)
opts=$(grep '^opts=' $1 | sed 's|^opts=||' | grep '^[a-zA-Z0-9_-][\s\.a-zA-Z0-9_-]*$' || true)
if [ "${hg}" = "" ] ; then
  echo "ERROR: Missing hostgroup"
  exit 1
fi
source $(dirname $0)/setup-env.sh ${hg}
ai-bs -g ${hg} ${opts}
