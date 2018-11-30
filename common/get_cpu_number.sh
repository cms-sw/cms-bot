#!/bin/bash -ex
ACTUAL_CPU=$(getconf _NPROCESSORS_ONLN)
case $(hostname) in lxplus* ) let ACTUAL_CPU=$ACTUAL_CPU/2 ;; esac
if [ "$ACTUAL_CPU" = "0" ] ; then ACTUAL_CPU=1; fi
if [ "X$1" != "X" ] ; then let ACTUAL_CPU=$ACTUAL_CPU$1 ; fi
echo ${ACTUAL_CPU}