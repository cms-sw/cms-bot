#!/usr/bin/env python
from commands import getstatusoutput as cmd
from os.path import getmtime,join
cache={}
e,o = cmd("ls -d wf*of*")
for d in o.split("\n"):
  s,s1=d.split(".list-",1)
  xt = int(getmtime(d)-getmtime(join(d,"jobs.json")))
  if not s in cache:cache[s]={}
  if not xt in cache[s]: cache[s][xt]=[]
  e, o = cmd("find %s -name 'workflow.log' -type f" % d)
  tp=0
  tf=0
  for l in o.split("\n"):
    e, o = cmd("grep 'tests passed' %s" % l)
    x = o.replace(" failed","").split(" tests passed, ")
    tp=tp+sum([int(i) for i in x[0].split(" ")])
    tf=tf+sum([int(i) for i in x[1].split(" ")])
  cache[s][xt].append({"order": s1, "passed": tp, "failed":tf})
for s in sorted(cache.keys()):
  print s
  for xt in sorted(cache[s].keys()):
    for item in cache[s][xt]:
      print "  ",xt,"  \t",item

