#!/usr/bin/env python
import json
from sys import argv, exit
from os.path import dirname, abspath
from commands import getstatusoutput as run_cmd
script_path = abspath(dirname(argv[0]))
eos_cmd = "/afs/cern.ch/project/eos/installation/cms/bin/eos.select"
eos_base = "/eos/cms/store/user/cmsbuild"
try:days=int(argv[1])
except: days=10
if days<10: days=10
e , o = run_cmd("PYTHONPATH=%s/.. %s/ib-datasets.py --days %s" % (script_path, script_path, days))
if e:
  print o
  exit(1)

jdata = json.loads(o)
used = {}

for o in jdata[0]['hits']['hits']:
  used[o['_source']['lfn']]=1

e, o = run_cmd("curl -s https://raw.githubusercontent.com/cms-sw/cms-sw.github.io/master/das_queries/ibeos.txt")
if e:
  print o
  exit(1)

total = 0
active = 0
unused = []
for l in o.split("\n"):
  total += 1
  if l in used:
    active += 1
    continue
  unused.append(l)
print "Total:",total
print "Active:",active
print "Unused:",len(unused)
if active == 0:
  print "No active file found. May be something went wrong"
  exit(1)
print "Renaming unused files"
for l in unused:
  pfn = "%s/%s" % (eos_base, l)
  e, o = run_cmd("%s stat -f %s" % (eos_cmd, pfn))
  if err:
    print o
    continue
  e, o = run_cmd("%s file rename %s %s.unused" % (eos_cmd, pfn, pfn))
  if e: print o
  else: print "Renamed: ",l

