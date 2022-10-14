#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
import sys, glob
from os.path import basename
from os.path import dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

WF_PATH=sys.argv[1]
for h in glob.glob(WF_PATH+"/*.html"):
  e, o = run_cmd("grep 'Skipped:\|Null:\|Fail:' '%s' | wc -l" % h)
  if (not e) and (int(o)==0):
    run_cmd("rm -f %s" % h)
print("Done filtering:", basename(WF_PATH))
