#!/bin/bash -x

baseA=$1
baseB=$2
diffN=$3
inList=$4

`dirname $0`/validateJR.py --base $baseA --ref $baseB
