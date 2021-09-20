#!/bin/bash
cmd=$1
if [ -f retry.txt ] ; then
  rm -f retry.txt
  echo "Previously done repos"
  ls *.done | wc -l
else
  rm -f *.done
fi
if ! $cmd "$@"  > run.log 2>&1 ; then
  cat run.log
  echo "Total done repos"
  ls *.done | wc -l
  if [ $(grep 'socket.timeout: timed out' run.log | wc -l) -gt 0 ] ; then
    echo "ERROR: Socket timeout, going to retry"
    let RETRY_COUNT=$RETRY_COUNT+1
    echo "RETRY_COUNT=$RETRY_COUNT" > retry.txt
    sleep 60
  else
    exit 1
  fi
else
  rm -rf *.done
fi
