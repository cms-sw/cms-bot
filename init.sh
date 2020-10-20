#!/bin/sh -ex

function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(nproc)
  if [ "X$1" != "X" ] ; then
    ACTUAL_CPU=$(echo "$ACTUAL_CPU*$1" | bc)
  fi
  echo $ACTUAL_CPU
}

