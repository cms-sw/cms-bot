#!/bin/bash -e
hg=$(head -1 $1 | grep '^hg=vocmssdt/' | sed 's|^hg=||' | grep '^[a-zA-Z0-9_/-][a-zA-Z0-9_/-]*$' || true)
if [ "$hg" = "" ] ; then
  echo "ERROR: Wrong hostgroup"
  exit 1
fi
ai-foreman -g "${hg}" --no-color --no-header -z Name -z OS showhost
