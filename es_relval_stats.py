#!/usr/bin/env python
from __future__ import print_function
from sys import exit, argv
from _py2with3compatibility import run_cmd
from os.path import isdir,basename,exists,join
import json
from es_utils import es_send_resource_stats
from hashlib import sha1
import threading
from time import sleep
import re

partial_log_dirpath=argv[1]
jobs=6
try: jobs=int(argv[2])
except: jobs=6
items = partial_log_dirpath.split("/")
if items[-1]!="pyRelValPartialLogs": exit(1)
release=items[-2]
arch=items[-6]
if not exists("%s/threads.txt" % partial_log_dirpath):
   e, o = run_cmd("grep ' --nThreads ' %s/*/cmdLog  | tail -1  | sed 's|.* *--nThreads *||;s| .*||'" % partial_log_dirpath)
   if e:
     print(o)
     exit(1)
   if not o: o="1"
   run_cmd("echo %s > %s/threads.txt" % (o, partial_log_dirpath))

e, o = run_cmd("head -1 %s/threads.txt" % partial_log_dirpath)
if e:
  print(o)
  exit(1)
cmsThreads = o.strip('\n')
e, o = run_cmd("ls -d %s/*" % partial_log_dirpath)
threads = []
for wf in o.split("\n"):
  if not isdir(wf): continue
  if exists(join(wf,"wf_stats.done")): continue
  wfnum = basename(wf).split("_",1)[0]
  hostname=""
  if exists(join(wf,"hostname")):
    hostname=open(join(wf,"hostname")).read().split("\n")[0]
  exit_codes={}
  if exists(join(wf,"workflow.log")):
    e, o = run_cmd("head -1 %s/workflow.log  | sed 's|.* exit: *||'" % wf)
    istep=0
    for e in [ int(x) for x in o.strip().split(" ") if x ]:
      istep+=1
      exit_codes["step%s" % istep ] = e
  e, o = run_cmd("ls %s/step*.log | sed 's|^.*/||'" % wf)
  steps = {}
  for log in o.split("\n"): steps[log.split("_")[0]]=""
  e, o = run_cmd("ls %s/wf_stats-step*.json" % wf)
  for s in o.split("\n"):
    step = s.split("/wf_stats-")[1][:-5]
    if step in steps: steps[step]=s
  for s in steps:
    sfile =steps[s]
    if sfile=="": continue
    exit_code=-1
    if s in exit_codes: exit_code = exit_codes[s]
    while True:
      threads = [t for t in threads if t.is_alive()]
      if(len(threads) >= jobs):sleep(0.5)
      else: break
    t = threading.Thread(target=es_send_resource_stats, args=(release, arch, wfnum, s, sfile, hostname, exit_code, params={"cmsthreads":cmsThreads}))
    t.start()
    threads.append(t)
  run_cmd("touch %s" % join(wf,"wf_stats.done"))
print("Active Threads:",len(threads))
for t in threads: t.join()

