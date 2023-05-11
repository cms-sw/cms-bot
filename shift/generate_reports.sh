#!/bin/bash
[ -d out ] && rm -rf out
git clone https://github.com/cms-sw/cmssdt-web.git
export PYTHONPATH=`pwd`/cmssdt-web/cgi-bin
python report.py
