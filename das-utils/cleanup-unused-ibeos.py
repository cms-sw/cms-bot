#!/usr/bin/env python
from __future__ import print_function
import json
from time import time
from sys import argv, exit
from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import top level modules
from _py2with3compatibility import run_cmd

script_path = abspath(dirname(argv[0]))
eos_cmd = "EOS_MGM_URL=root://eoscms.cern.ch /usr/bin/eos"
eos_base = "/eos/cms/store/user/cmsbuild"
unused_days_threshold = 180
try:
  days=int(argv[1])
except:
  days=30
if days<30:
  days=30
if (unused_days_threshold-days)<30: unused_days_threshold=days+30

e , o = run_cmd("PYTHONPATH=%s/.. %s/ib-datasets.py --days %s" % (script_path, script_path, days))
if e:
  print(o)
  exit(1)

jdata = json.loads(o)
used = {}
for o in jdata['hits']['hits']:
  used[o['_source']['lfn'].strip()]=1

e, o = run_cmd("%s find -f %s" % (eos_cmd, eos_base))
if e:
  print(o)
  exit(1)

total = 0
active = 0
unused = []
all_files = []
for l in o.split("\n"):
  l = l.replace(eos_base,"")
  all_files.append(l)
  if not l.endswith(".root"): continue
  total += 1
  if l in used:
    active += 1
    continue
  unused.append(l)

print("Total:",total)
print("Active:",active)
print("Unused:",len(unused))
if active == 0:
  print("No active file found. May be something went wrong")
  exit(1)

print("Renaming unused files")
for l in unused:
  if not l in all_files: continue
  pfn = "%s/%s" % (eos_base, l)
  e, o = run_cmd("%s stat -f %s" % (eos_cmd, pfn))
  if e:
    print(o)
    continue
  e, o = run_cmd("%s file rename %s %s.unused" % (eos_cmd, pfn, pfn))
  if e:
    print(o)
  else:
    print("Renamed: ",l)
    run_cmd("%s file touch %s.unused" % (eos_cmd, pfn))
print("Removing %s days old unused files." % unused_days_threshold)
for unused_file in all_files:
  if not unused_file.endswith(".unused"): continue
  unused_file = "%s/%s" % (eos_base, unused_file)
  e, o = run_cmd("%s fileinfo %s | grep 'Modify:' | sed 's|.* Timestamp: ||'" % (eos_cmd, unused_file))
  if e or (o == ""):
    print("Error: Getting timestamp for %s\n%s" % (unused_file, o))
    continue
  unused_days = int((time()-float(o))/86400)
  if unused_days<unused_days_threshold: continue
  print("Deleting as unused for last %s days: %s" % (unused_days, unused_file))
  run_cmd("%s rm %s" % (eos_cmd, unused_file))
