#!/bin/bash -ex
python3 -m venv venv
source venv/bin/activate
if [ $(python3 -c "import sys;print(sys.version_info[1])") -gt 6 ] ; then
  pip install CMSMonitoring==0.3.3
else
  pip install --user CMSMonitoring==0.3.3
fi
python3 $(dirname $0)/ib-profiling-data.py
