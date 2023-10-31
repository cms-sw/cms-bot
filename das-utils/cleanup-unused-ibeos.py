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
unused_days_threshold = 360
try:
    days = int(argv[1])
except:
    days = 30
if days < 30:
    days = 30
if (unused_days_threshold - days) < 180:
    unused_days_threshold = days + 180
active_days_threshold = int(unused_days_threshold / 2)


def get_unused_days(eosfile):
    e, o = run_cmd(
        "%s fileinfo %s | grep 'Modify:' | sed 's|.* Timestamp: ||'" % (eos_cmd, eosfile)
    )
    if e or (o == ""):
        print("Error: Getting timestamp for %s\n%s" % (eosfile, o))
        return -1
    return int((time() - float(o)) / 86400)


e, o = run_cmd("PYTHONPATH=%s/.. %s/ib-datasets.py --days %s" % (script_path, script_path, days))
if e:
    print(o)
    exit(1)

jdata = json.loads(o)
used = {}
for o in jdata["hits"]["hits"]:
    used[o["_source"]["lfn"].strip()] = 1

e, o = run_cmd("%s find -f %s" % (eos_cmd, eos_base))
if e:
    print(o)
    exit(1)

total = 0
active = 0
unused = []
all_files = []
for pfn in o.split("\n"):
    l = pfn.replace(eos_base, "")
    if not l.startswith("/store/"):
        if l.endswith(".root.unused"):
            pfn = pfn.replace(".root.unused", ".root")
            run_cmd("%s file rename %s.unused %s" % (eos_cmd, pfn, pfn))
        continue
    all_files.append(l)
    if not l.endswith(".root"):
        continue
    total += 1
    if l in used:
        run_cmd("%s file touch %s" % (eos_cmd, pfn))
        active += 1
        continue
    unused_days = get_unused_days(pfn)
    print("%s unused for last %s days." % (pfn, unused_days))
    if (unused_days + days) < active_days_threshold:
        active += 1
    else:
        unused.append(l)

print("Total:", total)
print("Active:", active)
print("Unused:", len(unused))
if active == 0:
    print("No active file found. May be something went wrong")
    exit(1)

print("Renaming unused files")
for l in unused:
    pfn = "%s/%s" % (eos_base, l)
    e, o = run_cmd("%s stat -f %s" % (eos_cmd, pfn))
    if e:
        print(o)
        continue
    e, o = run_cmd("%s file rename %s %s.unused" % (eos_cmd, pfn, pfn))
    if e:
        print(o)
    else:
        print("Renamed: ", l)
        run_cmd("%s file touch %s.unused" % (eos_cmd, pfn))
print("Removing %s days old unused files." % unused_days_threshold)
for unused_file in all_files:
    if not unused_file.endswith(".unused"):
        continue
    unused_file = "%s/%s" % (eos_base, unused_file)
    unused_days = get_unused_days(unused_file)
    if unused_days < unused_days_threshold:
        continue
    print("Deleting as unused for last %s days: %s" % (unused_days, unused_file))
    run_cmd("%s rm %s" % (eos_cmd, unused_file))
