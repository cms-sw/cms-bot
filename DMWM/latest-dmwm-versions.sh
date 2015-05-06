#! /bin/bash -e

export WMAGENT_LATEST=$(curl -s http://cmsrep.cern.ch/cmssw/comp.pre/RPMS/$DMWM_ARCH/ | cut -d\> -f6 | cut -d\" -f2 | grep wmagent-dev | cut -d+ -f3 | rev | cut -d\- -f3- | rev | tail -1)

