#!/usr/bin/env python3
from os.path import dirname, abspath
import sys, re

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, cmsbot_dir)

from es_utils import get_indexes, close_index, find_indexes, open_index
from cmsutils import epoch2week
from time import time

try:
    weeks = int(sys.argv[1])
except:
    weeks = 20
ignore_index = []
for idx in sys.argv[2:]:
    ignore_index.append(idx)
cur_week = int(epoch2week(time(), 1))
idxs = []
odxs = []
try:
    if sys.argv[2]:
        for ix in sys.argv[2:]:
            ixs = find_indexes(ix)
            if not "open" in ixs:
                continue
            for i in ixs["open"]:
                idxs.append(i)
except:
    types = {"close": {}, "open": {}}
    rest = {"close": [], "open": []}
    ixs = find_indexes("cmssdt-*")
    for k in ixs:
        for idx in ixs[k]:
            m = re.match(r"^(.+)[_-]([\d]+)$", idx)
            if m:
                ix = m.group(1)
                wk = m.group(2)
                if not k in types:
                    types[k] = {}
                if not ix in types[k]:
                    types[k][ix] = []
                types[k][ix].append(wk)
                if ix in ignore_index:
                    continue
                if (k == "open") and ((cur_week - int(wk)) > weeks):
                    idxs.append(idx)
                if (k == "close") and ((cur_week - int(wk)) <= weeks):
                    odxs.append(idx)
            else:
                if not k in rest:
                    rest[k] = []
                rest[k].append(idx)
    for k in rest:
        print("REST:", k, ":", sorted(rest[k]))
    for k in types:
        for ix in sorted(types[k].keys()):
            print("WEEK:", k, ":", ix, sorted(types[k][ix]))

for idx in sorted(idxs):
    print("Closing ", idx)
    close_index(idx)
    print("  ", get_indexes(idx).strip())

for idx in sorted(odxs):
    print("Opening ", idx)
    open_index(idx)
    print("  ", get_indexes(idx).strip())
