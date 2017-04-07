#!/usr/bin/env python
from sys import exit, argv
from commands import getstatusoutput
from os.path import isdir,basename,exists,join
import json
from datetime import datetime
from es_utils import send_payload_old as send_payload
from hashlib import sha1

def percentile(percentage, data, dlen):
  R=(dlen+1)*percentage/100.0
  IR=int(R)
  if IR>=dlen: return data[-1]
  elif IR==0: return data[0]
  FR=int((R-IR)*100)
  res = data[IR-1]
  if FR>0: res=(FR/100.0)*(data[IR]-res)+res
  return res

partial_log_dirpath=argv[1]
items = partial_log_dirpath.split("/")
if items[-1]!="pyRelValPartialLogs": exit(1)
release=items[-2]
arch=items[-6]
rel_sec  = int(datetime.strptime(release.split("_")[-1], '%Y-%m-%d-%H%M').strftime('%s'))
rel_msec = rel_sec*1000
week     = str(int(((rel_sec/86400)+4)/7))
ex_fields=["rss", "vms", "pss", "uss", "shared", "data", "cpu"]
e, o = getstatusoutput("ls -d %s/*" % partial_log_dirpath)
for wf in o.split("\n"):
  if not isdir(wf): continue
  if exists(join(wf,"wf_stats.done")): continue
  wfnum = basename(wf).split("_",1)[0]
  e, o = getstatusoutput("ls %s/step*.log | sed 's|^.*/||'" % wf)
  steps = {}
  for log in o.split("\n"): steps[log.split("_")[0]]=""
  e, o = getstatusoutput("ls %s/wf_stats-step*.json" % wf)
  for s in o.split("\n"):
    step = s.split("/wf_stats-")[1][:-5]
    if step in steps: steps[step]=s
  for s in steps:
    sfile =steps[s]
    if sfile=="": continue
    try:
      stats = json.load(open(sfile))
      xdata = {}
      count=0
      for stat in stats:
        count+=1
        for item in stat:
          try: xdata[item].append(stat[item])
          except:
            xdata[item]=[]
            xdata[item].append(stat[item])
        stat["@timestamp"]=rel_msec+(stat["time"]*1000)
        stat["type"]="partial"
        stat["release"]=release
        stat["step"]=s
        stat["workflow"]=wfnum
        stat["architecture"]=arch
        idx = sha1("partial" + release + arch + wfnum + s + str(stat["time"])).hexdigest()
        del stat["time"]
        try:send_payload("relvals_stats_"+week,"runtime-stats",idx,json.dumps(stat))
        except Exception as e: print e
      print release, arch, wfnum, s, count
      sdata = {"type":"full", "release":release, "architecture":arch, "step":s, "@timestamp":rel_msec, "workflow":wfnum}
      for x in xdata:
        data = sorted(xdata[x])
        if x in ["time","num_threads","processes","num_fds"]:
          sdata[x]=data[-1]
          continue
        if not x in ex_fields: continue
        dlen = len(data)
        for t in ["min", "max", "avg", "median", "25", "50", "75", "80", "85", "90", "95"]: sdata[x+"_"+t]=0
        if dlen>0:
          sdata[x+"_min"]=data[0]
          sdata[x+"_max"]=data[-1]
          if dlen>1:
            dlen2=int(dlen/2)
            if (dlen%2)==0: sdata[x+"_median"]=int((data[dlen2-1]+data[dlen2])/2)
            else: sdata[x+"_median"]=data[dlen2]
            sdata[x+"_avg"]=int(sum(data)/dlen)
            for t in [25, 50, 75, 80, 85, 90, 95]:
              sdata[x+"_"+str(t)]=int(percentile(t,data, dlen))
          else:
            for t in ["25", "50", "75", "80", "85", "90", "95", "avg", "median"]:
              sdata[x+"_"+t]=data[0]
      idx = sha1("full" + release + arch + wfnum + s + str(rel_sec)).hexdigest()
      try:send_payload("relvals_stats_"+week,"runtime-stats",idx,json.dumps(sdata))
      except Exception as e: print e
    except Exception as e: print e
  getstatusoutput("touch %s" % join(wf,"wf_stats.done"))
