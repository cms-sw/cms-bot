#!/usr/bin/env python
from os import system, getpid
from sys import argv, exit
from time import sleep, time
import psutil
from threading import Thread

job = {'exit_code':0, 'command':'true'}
def run_job(job): job['exit_code']=system(job['command'])

def update_stats(proc, stats):
  clds = len(proc.children())
  if clds==0: return
  stats['processes'] += clds
  for cld in proc.children():
    update_stats(cld, stats)
    mem = cld.memory_full_info()
    for a in ["rss", "vms", "shared", "data", "uss", "pss"]: stats[a]+=getattr(mem,a)
    stats['num_fds'] += cld.num_fds()
    stats['num_threads'] += cld.num_threads()

def monitor(stop):
  p = psutil.Process(getpid())
  data = []
  stime = int(time())
  while not stop():
    xdata = {"rss":0, "vms":0, "shared":0, "data":0, "uss":0, "pss":0,"num_fds":0,"num_threads":0, "processes":0}
    update_stats(p, xdata)
    xdata['time'] = int(time()-stime)
    data.append(xdata)
    for i in range(5):
      sleep(1)
      if stop(): break
  from json import dump
  stat_file =open("wf_stats-%s.json" % stime,"w")
  dump(data, stat_file)
  stat_file.close()
  return

stop_monitoring = False
job['command']=" ".join(argv[1:])
job_thd = Thread(target=run_job, args=(job,))
mon_thd = Thread(target=monitor, args=(lambda: stop_monitoring,))
job_thd.start()
mon_thd.start()
job_thd.join()
stop_monitoring = True
mon_thd.join()
exit(job['exit_code'])

