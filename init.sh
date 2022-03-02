#!/bin/sh -ex

function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(nproc)
  if [ "X$1" != "X" ] ; then
    let ACTUAL_CPU=$ACTUAL_CPU*$1 || true
  fi
  echo $ACTUAL_CPU
}

