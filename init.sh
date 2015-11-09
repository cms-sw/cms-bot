#!/bin/sh -ex
function Jenkins_GetCPU ()
{
  ACTUAL_CPU=$(getconf _NPROCESSORS_ONLN)
  case $NODE_NAME in
    lxplus* ) ACTUAL_CPU=$(echo $ACTUAL_CPU / 2 | bc) ;;
  esac
  if [ "X$1" != "X" ] ; then
    ACTUAL_CPU=$(echo "$ACTUAL_CPU*$1" | bc)
  fi
  echo $ACTUAL_CPU
}

