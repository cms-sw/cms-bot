#!/bin/bash -ex
source $(dirname $0)/utils.sh
cvmfs_transaction $1
