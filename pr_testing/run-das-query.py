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
e, o = run_cmd(cmd)
print(o)
if e: sys.exit(1)
