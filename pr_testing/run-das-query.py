#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
import os, sys
BOT_DIR=os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
sys.path.insert(0,BOT_DIR)
from _py2with3compatibility import run_cmd
from cmsutils import MachineCPUCount
from RelValArgs import GetMatrixOptions

os.environ["PATH"] = "%s/das-utils:%s" % (BOT_DIR, os.environ["PATH"])
cmd = "runTheMatrix.py -j %s --maxSteps=0 %s" % (MachineCPUCount, GetMatrixOptions(os.environ["CMSSW_VERSION"], os.environ["SCRAM_ARCH"]))
print("Running ",cmd)
e, o = run_cmd("touch runall-report-step123-.log ; rm -rf rel; mkdir rel; cd rel; %s;  [ -f runall-report-step123-.log ] && cp runall-report-step123-.log ../" % cmd)
print(o)
err=0
if e: err=1
if os.getenv("MATRIX_EXTRAS",""):
  e, o = run_cmd("grep -E '^[1-9][0-9]*(\.[0-9]*|)_' runall-report-step123-.log | sed 's|_.*||'")
  all_wfs = [wf for wf in o.split('\n') if wf]
  print("All WFS:",all_wfs)
  new_wfs = []
  for wf in os.getenv("MATRIX_EXTRAS","").split(","):
    if wf and (not wf in all_wfs) and (not wf in new_wfs): new_wfs.append(wf)
  print("New WFs:",new_wfs)
  if new_wfs:
    cmd = "%s -l %s %s" % (cmd, ','.join(new_wfs), os.getenv("EXTRA_MATRIX_ARGS",""))
    print("Running ",cmd)
    e, o = run_cmd("rm -rf rel; mkdir rel; cd rel; %s ; [ -f runall-report-step123-.log ] && cat runall-report-step123-.log >> ../runall-report-step123-.log" % cmd)
    print(o)
    if e: err=1
sys.exit(err)
