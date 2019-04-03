#!/usr/bin/env python
from sys import stdin, exit, version_info
if version_info[0] == 2:
  from commands import getstatusoutput as run_cmd
else:
  from subprocess import getstatusoutput as run_cmd
all_dasfiles = []
new_order    = []
for line in stdin:
  line = line.strip("\n")
  if line.startswith("/store/"): all_dasfiles.append(line)
  else: new_order.append(line)

if not all_dasfiles:
  print("\n".join(new_order))
  exit(0)

eos_cmd = "EOS_MGM_URL=root://eoscms.cern.ch /usr/bin/eos"
EOS_BASE="/eos/cms/store/user/cmsbuild/store"
eos_base_len = len(EOS_BASE)
err, eos_files = run_cmd("%s find -f %s | sort" % (eos_cmd,EOS_BASE))
if err:
  print("\n".join(new_order))
  exit(0)

new_order = []
for eos_file in eos_files.split("\n"):
  eos_file="/store"+eos_file[eos_base_len:]
  if eos_file in all_dasfiles: new_order.append(eos_file)
for das_file in all_dasfiles:
  if not das_file in new_order: new_order.append(das_file)

print("\n".join(new_order))