#!/usr/bin/env python
from os import system, getpid
from sys import argv, exit
from time import sleep, time
import psutil
from threading import Thread

job = {'exit_code':0, 'command':'true'}
def run_job(job): job['exit_code']=system(job['command'])

def update_stats(proc):
  stats = {"rss":0, "vms":0, "shared":0, "data":0, "uss":0, "pss":0,"num_fds":0,"num_threads":0, "processes":0}
  children = proc.children(recursive=True)
  clds = len(children)
  if clds==0: return stats
  stats['processes'] = clds
  for cld in children:
    try:
      mem   = cld.memory_full_info()
      fds   = cld.num_fds()
      thrds = cld.num_threads()
      stats['num_fds'] += fds
      stats['num_threads'] += thrds
      for a in ["rss", "vms", "shared", "data", "uss", "pss"]: stats[a]+=getattr(mem,a)
    except:pass
  return stats

def monitor(stop, stime):
  p = psutil.Process(getpid())
  data = []
  while not stop():
    try:
      stats = update_stats(p)
      if stats['processes']>0:
        stats['time'] = int(time()-stime)
        data.append(stats)
    except: pass
    for i in range(5):
      sleep(1)
      if stop(): break
  from json import dump
  stat_file =open("wf_stats-%s.json" % stime,"w")
  dump(data, stat_file)
  stat_file.close()
  return

stime = int(time())
#Always create the stats file
stat_file =open("wf_stats-%s.json" % stime,"w")
stat_file.write("[]");
stat_file.close()

stop_monitoring = False
job['command']=" ".join(argv[1:])
job_thd = Thread(target=run_job, args=(job,))
mon_thd = Thread(target=monitor, args=(lambda: stop_monitoring, stime))
job_thd.start()
mon_thd.start()
job_thd.join()
stop_monitoring = True
mon_thd.join()
exit(job['exit_code'])

