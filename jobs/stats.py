#!/usr/bin/env python
from __future__ import print_function
import sys
from os.path import getmtime, join, dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

cache={}
e,o = run_cmd("ls -d wf*of*")
for d in o.split("\n"):
  s,s1=d.split(".list-",1)
  xt = int(getmtime(d)-getmtime(join(d,"jobs.json")))
  if not s in cache:cache[s]={}
  if not xt in cache[s]: cache[s][xt]=[]
  e, o = run_cmd("find %s -name 'workflow.log' -type f" % d)
  tp=0
  tf=0
  for l in o.split("\n"):
    e, o = run_cmd("grep 'tests passed' %s" % l)
    x = o.replace(" failed","").split(" tests passed, ")
    tp=tp+sum([int(i) for i in x[0].split(" ")])
    tf=tf+sum([int(i) for i in x[1].split(" ")])
  cache[s][xt].append({"order": s1, "passed": tp, "failed":tf})
for s in sorted(cache.keys()):
  print(s)
  for xt in sorted(cache[s].keys()):
    for item in cache[s][xt]:
      print("  ",xt,"  \t",item)

