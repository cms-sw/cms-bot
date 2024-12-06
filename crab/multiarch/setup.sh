#!/bin/bash -ex
for f in minbias.root FrameworkJobReport.xml ; do 
  curl -L -s -o $CMSSW_BASE/src/$f http://cern.ch/muzaffar/$f
done
