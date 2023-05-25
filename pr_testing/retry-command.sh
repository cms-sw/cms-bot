#!/bin/bash
max_try=1
if [ $(echo "${CMS_BOT_RETRY_COUNT}" | grep '^[1-9]$' | wc -l) -gt 0 ] ; then
  max_try=${CMS_BOT_RETRY_COUNT}
fi
while true ; do
  let max_try=$max_try-1
  echo "Running $@"
  $@
  err=$?
  if [ $err -gt 0 ] ; then
    [ $max_try -gt 0 ] || exit $err
  else
    exit 0
  fi
done
