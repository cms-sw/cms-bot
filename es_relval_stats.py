#!/usr/bin/env python
from __future__ import print_function
from sys import exit, argv
from _py2with3compatibility import run_cmd
from os.path import isdir,basename,exists,join
import json
from es_utils import send_payload
from cmsutils import cmsswIB2Week
from hashlib import sha1
import threading
from time import sleep
import re

ReReleaseQueue = re.compile('(.*_X)_')

def percentile(percentage, data, dlen):
  R=(dlen+1)*percentage/100.0
  IR=int(R)
  if IR>=dlen: return data[-1]
  elif IR==0: return data[0]
  FR=int((R-IR)*100)
  res = data[IR-1]
  if FR>0: res=(FR/100.0)*(data[IR]-res)+res
  return res

def process(wfnum, s, sfile, hostname, exit_code, details=False):
  global release, arch, rel_msec, week, ex_fields, cmsThreads
  release_queue = ReReleaseQueue.match(release).group(1)

  try:
    stats = json.load(open(sfile))
    xdata = {}
    for stat in stats:
      for item in stat:
        try: xdata[item].append(stat[item])
        except:
          xdata[item]=[]
          xdata[item].append(stat[item])
      stat["@timestamp"]=rel_msec+(stat["time"]*1000)
      stat["release"]=release
      stat["release_queue"] = release_queue
      stat["step"]=s
      stat["workflow"]=wfnum
      stat["cmsthreads"]=cmsThreads
      stat["architecture"]=arch
      idx = sha1(release + arch + wfnum + s + str(stat["time"])).hexdigest()
      del stat["time"]
      if details:
        try:send_payload("relvals_stats_details-"+week,"runtime-stats-details",idx,json.dumps(stat))
        except Exception as e: print(e)
    print("Working on ",release, arch, wfnum, s, len(stats))
    sdata = {"release":release, "release_queue": release_queue,"architecture":arch, "step":s, "@timestamp":rel_msec,
             "workflow":wfnum, "hostname":hostname, "exit_code":exit_code, "cmsthreads":cmsThreads}
    for x in xdata:
      data = sorted(xdata[x])
      if x in ["time","num_threads","processes","num_fds"]:
        sdata[x]=data[-1]
        continue
      if not x in ex_fields: continue
      dlen = len(data)
      for t in ["min", "max", "avg", "median", "25", "75"]: sdata[x+"_"+t]=0
      if dlen>0:
        sdata[x+"_min"]=data[0]
        sdata[x+"_max"]=data[-1]
        if dlen>1:
          dlen2=int(dlen/2)
          if (dlen%2)==0: sdata[x+"_median"]=int((data[dlen2-1]+data[dlen2])/2)
          else: sdata[x+"_median"]=data[dlen2]
          sdata[x+"_avg"]=int(sum(data)/dlen)
          for t in [25, 75]:
            sdata[x+"_"+str(t)]=int(percentile(t,data, dlen))
        else:
          for t in ["25", "75", "avg", "median"]:
            sdata[x+"_"+t]=data[0]
    idx = sha1(release + arch + wfnum + s + str(rel_sec)).hexdigest()
    try:send_payload("relvals_stats_summary-"+week,"runtime-stats-summary",idx,json.dumps(sdata))
    except Exception as e: print(e)
  except Exception as e: print(e)
  return

partial_log_dirpath=argv[1]
jobs=6
try: jobs=int(argv[2])
except: jobs=6
items = partial_log_dirpath.split("/")
if items[-1]!="pyRelValPartialLogs": exit(1)
release=items[-2]
arch=items[-6]
week, rel_sec  = cmsswIB2Week(release)
rel_msec = rel_sec*1000
ex_fields=["rss", "vms", "pss", "uss", "shared", "data", "cpu"]
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
    t = threading.Thread(target=process, args=(wfnum, s, sfile, hostname, exit_code))
    t.start()
    threads.append(t)
  run_cmd("touch %s" % join(wf,"wf_stats.done"))
print("Active Threads:",len(threads))
for t in threads: t.join()

