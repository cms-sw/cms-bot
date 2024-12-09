#!/bin/bash -ex
git cms-addpkg FWCore/Framework
cp $(dirname $0)/Makefile.rules ${CMSSW_BASE}/config/SCRAM/GMake/Makefile.rules
