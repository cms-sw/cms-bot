#!/bin/bash -ex
cmd=$1 ; shift
if [ -f retry.txt ] ; then
  rm -f retry.txt
  echo "Previously done repos"
  ls *.done | wc -l
else
  rm -f *.done
fi
if ! $cmd ${1+"$@"}  > run.log 2>&1 ; then
  cat run.log
  echo "Total done repos"
  ls *.done | wc -l
  if [ $(grep -E '(socket.timeout: timed out|ssl.SSLError:)' run.log | wc -l) -gt 0 ] ; then
    echo "ERROR: Socket timeout, going to retry"
    let RETRY_COUNT=$RETRY_COUNT+1
    echo "RETRY_COUNT=$RETRY_COUNT" > retry.txt
    sleep 60
  else
    exit 1
  fi
else
  cat run.log
  rm -rf *.done
fi
