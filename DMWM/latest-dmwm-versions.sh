#! /bin/bash -e

export WMAGENT_LATEST=$(curl -s "http://cmsrep.cern.ch/cgi-bin/repos/$COMP_REPO/$DMWM_ARCH?C=M;O=D" | grep -oP "(?<=>cms\+wmagent-dev\+).*(?=-1-1)" | head -1)
export WMAGENTPY3_LATEST=$(curl -s "http://cmsrep.cern.ch/cgi-bin/repos/$COMP_REPO/$DMWM_ARCH?C=M;O=D" | grep -oP "(?<=>cms\+wmagentpy3-dev\+).*(?=-1-1)" | head -1)
export CRABDEV_LATEST=$(curl -s "http://cmsrep.cern.ch/cgi-bin/repos/$COMP_REPO/$DMWM_ARCH?C=M;O=D" | grep -oP "(?<=>cms\+crab-devtools\+).*(?=-1-1)" | head -1)
