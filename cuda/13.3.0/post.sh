#!/bin/bash
wget https://raw.githubusercontent.com/cms-sw/cmsdist/refs/heads/IB/CMSSW_20_1_X/master/patches/cuda_cccl_8771.patch
patch -d include/cccl -p2 < cuda_cccl_8771.patch 
