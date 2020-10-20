#!/bin/bash -e
ACTUAL_CPU=$(nproc)
if [ "$ACTUAL_CPU" = "0" ] ; then ACTUAL_CPU=1; fi
if [ "X$1" != "X" ] ; then let ACTUAL_CPU=$ACTUAL_CPU$1 ; fi
echo ${ACTUAL_CPU}
