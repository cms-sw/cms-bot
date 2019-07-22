#!/usr/bin/env python
from __future__ import print_function
from os.path import dirname, abspath
import sys, re

# TODO are these script used?
cmsbot_dir=None
if __file__: cmsbot_dir=dirname(dirname(abspath(__file__)))
else: cmsbot_dir=dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0,cmsbot_dir)

from es_utils import get_indexes, close_index, find_indexes
from time import time
cur_week=int(((time()/86400)+4)/7)

idxs=[]
try:
  if sys.argv[1]:
    for ix in sys.argv[1:]:
      ixs = find_indexes(ix)
      if not "open" in ixs: continue
      for i in ixs["open"]: idxs.append(i)
except:
  types = {"close":{}, "open":{}}
  rest  = {"close":[], "open":[]}
  ixs = find_indexes('cmssdt-*')
  for k in ixs:
    for idx in ixs[k]:
      m = re.match("^(.+)[_-]([\d]+)$",idx)
      if m:
        ix = m.group(1)
        wk = m.group(2)
        if not k in types: types[k]={}
        if not ix in types[k]:types[k][ix]=[]
        types[k][ix].append(wk)
        if (k == "open") and ((cur_week-int(wk))>4): idxs.append(idx)
      else:
        if not k in rest: rest[k]=[]
        rest[k].append(idx)
  for k in rest:
    print("REST:", k, ":", sorted(rest[k]))
  for k in types:
    for ix in sorted(types[k].keys()):
      print("WEEK:",k,":",ix,sorted(types[k][ix]))

for idx in sorted(idxs):
  print("Closing ",idx)
  close_index(idx)
  print("  ",get_indexes(idx).strip())
