#!/usr/bin/env python3
from __future__ import print_function
import sys,re

def read_workflows(wfile):
  fin = open(wfile)
  data = {}
  wf = ""
  for line in fin.readlines():
    m = re.match("^([^[]+)\[(\d+)]:\s+(.+)",line)
    if m:
      cmd = re.sub("\s\s+"," ",m.group(3).strip())
      if m.group(1).strip():
        wf = m.group(1).strip().split(" ",1)[0]
        data [wf] = []
      data[wf].append(cmd)
  return data

orig = sys.argv[1]
new = sys.argv[2]

odata= read_workflows(orig)
ndata = read_workflows(new)

cdata = {}
for wf in ndata:
  cdata[wf] = []
  if not wf in odata:
    cdata[wf] = ["New workflow"]
    continue
  nlen = len(ndata[wf])
  olen = len(odata[wf])
  if nlen!=olen:
    cdata[wf] = ["Number of Steps changed: %s vs %s" % (olen, nlen)]
  else:
    for i in range(nlen):
      if ndata[wf][i]!=odata[wf][i]:
        cdata[wf].append("\n    - **step%s**\n```\n- %s\n+ %s\n```" % (i+1, ndata[wf][i],odata[wf][i]))
wfs = sorted(cdata, key=float)
for wf in wfs:
  if not cdata[wf]: continue
  if len(cdata[wf])==1:
    print ("  - **%s**: %s" % (wf, cdata[wf][0]))
  else:
    print ("  - **%s**:" % wf)
    for c in cdata[wf]:
      print (c)
