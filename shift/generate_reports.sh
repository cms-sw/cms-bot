#!/bin/bash
[ -d out ] && rm -rf out
[ ! -d cmssdt-web ] && git clone https://github.com/cms-sw/cmssdt-web.git || (cd cmssdt-web; git reset --HARD; git pull -q --rebase)
export PYTHONPATH=`pwd`/cmssdt-web/cgi-bin
python report.py
