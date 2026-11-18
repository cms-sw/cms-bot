#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

import sys
from sys import stdin, exit

from os.path import dirname, abspath

sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

all_dasfiles = []
new_order = []
for line in stdin:
    line = line.strip("\n")
    if line.startswith("/store/"):
        all_dasfiles.append(line)
    else:
        new_order.append(line)

if not all_dasfiles:
    print("\n".join(new_order))
    exit(0)

eos_cmd = "EOS_MGM_URL=root://eoscms.cern.ch /usr/bin/eos"
EOS_BASE = "/eos/cms/store/user/cmsbuild/store"
eos_base_len = len(EOS_BASE)
err, eos_files = run_cmd("%s find -f %s | sort" % (eos_cmd, EOS_BASE))
if err:
    print("\n".join(new_order))
    exit(0)

new_order = []
for eos_file in eos_files.split("\n"):
    eos_file = "/store" + eos_file[eos_base_len:]
    if eos_file in all_dasfiles:
        new_order.append(eos_file)
for das_file in all_dasfiles:
    if not das_file in new_order:
        new_order.append(das_file)

print("\n".join(new_order))
