#!/usr/bin/env python3
from sys import exit
from os.path import abspath, dirname, exists, getmtime
import json
from hashlib import sha256
from threading import Thread
from time import sleep, time
import re
import sys
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import getstatusoutput

eos_cmd = "EOS_MGM_URL=root://eoscms.cern.ch /usr/bin/eos"
eos_base = "/eos/cms/store/user/cmsbuild"
opts = None

def get_alive_threads(threads):
  alive = []
  for t in threads:
    if t.is_alive(): alive.append(t)
  return alive

try:
  CMS_BOT_DIR = dirname(abspath(__file__))
except Exception as e :
  from sys import argv
  CMS_BOT_DIR = dirname( abspath(argv[0]))

def run_cmd(cmd, exit_on_error=True,debug=True):
  if debug: print(">> %s" % cmd)
  err, out = getstatusoutput(cmd)
  if err:
    if exit_on_error:
      print(out)
      exit(1)
  return err, out

def get_lfns_from_kibana(days=7):
  print("Getting information from CMS Elasticsearch....")
  kibana_file = "lfn_kibana.json"
  cmd = "PYTHONPATH=%s/.. %s/ib-datasets.py --days %s > %s; cat %s" % (CMS_BOT_DIR, CMS_BOT_DIR, days, kibana_file, kibana_file)
  if exists(kibana_file): cmd = "cat %s" % kibana_file
  err, from_kibaba = run_cmd(cmd)
  print("Collecting unique LFN from Kibana ....")
  used_lfns = {}
  for hit in json.loads(from_kibaba)["hits"]["hits"]:
    if not "_source"  in hit: continue
    if not "lfn" in hit["_source"]: continue
    lfn = hit["_source"]["lfn"].strip()
    if (not lfn) or ("/store/user/cmsbuild" in lfn): continue
    used_lfns[lfn]=1
  return list(used_lfns.keys())

def get_lfns_from_das(lfn_per_query=1):
  if lfn_per_query<1: return []
  print("Getting information from DAS queries....")
  err, out = run_cmd("test -d cms-sw.github.io || git clone --depth 1 https://github.com/cms-sw/cms-sw.github.io.git")
  err, qfiles = run_cmd("ls cms-sw.github.io/das_queries/*/*.query")
  used_lfns = {}
  for qfile in qfiles.split("\n"):
    lfn_file = qfile.strip()[:-6]
    if not exists(lfn_file): continue
    lfn_count = 0
    err, out = run_cmd("grep '/store/' %s" % lfn_file,debug=False, exit_on_error=False)
    for lfn in out.split("\n"):
      if not "/store/" in lfn: continue
      lfn = lfn.strip("\n").replace('"',"").replace(',',"").strip(" ")
      used_lfns[lfn]=1
      lfn_count += 1
      if lfn_count>=lfn_per_query: break
  return list(used_lfns.keys())

def get_lfns_for_cmsbuild_eos(lfn_per_query=1, days=7):
  das_lfns    = get_lfns_from_das(lfn_per_query)
  kibana_lfns = get_lfns_from_kibana(days)
  eos_lfns = {}
  for lfn in kibana_lfns+das_lfns: eos_lfns[lfn.strip()]=1
  print("LFNs from Kibana: %s" % len(kibana_lfns))
  print("LFNs from DAS Queries: %s" % len(das_lfns))
  print("Total LFNs: %s" % len(eos_lfns))
  return list(eos_lfns.keys())

def copy_to_eos(lfn, log_file):
  cmd = "%s/copy-ib-lfn-to-eos.sh %s %s >%s 2>&1" % (CMS_BOT_DIR, lfn, opts.redirector,log_file)
  run_cmd(cmd,exit_on_error=False,debug=False)
  e, o = run_cmd("grep ' echo ALL_OK' %s" % log_file, exit_on_error=False,debug=False)
  if 'ALL_OK' in o:
    print("  Success: %s" % lfn)
  else:
    print("  Failed: %s" % lfn)
  return

def kill_xrootd(lfn):
  print("  Requested to kill %s" % lfn)
  err, out = run_cmd("pgrep -l -f '.*/copy-ib-lfn-to-eos.sh %s .*'" % lfn)
  pids = ""
  for process in out.split("\n"):
    if 'pgrep ' in process: continue
    items = process.split(" ",1)
    pids = pids+" "+process.split(" ",1)[0]
  if pids:
    print("  Killing %s" % pids)
    run_cmd("kill -9 %s" % pids,exit_on_error=False,debug=False)
    run_cmd("%s rm %s%s.tmp" % (eos_cmd,eos_base, lfn),exit_on_error=False,debug=False)

def eos_exists(eos_file):
  err, out = run_cmd("%s stat -f %s" % (eos_cmd, eos_file),exit_on_error=False,debug=False)
  if err: return False
  return True

def eos_rename(name, new_name):
  print("  Rename: %s -> %s" % (name, new_name))
  err, out = run_cmd("%s file rename %s %s" % (eos_cmd, name, new_name),exit_on_error=False,debug=False)
  if err:
    print(out)
    return False
  return True

def eos_size(eos_file):
  if not eos_exists(eos_file): return -1
  err, out = run_cmd("%s ls -l %s | awk '{print $5}'" % (eos_cmd, eos_file), debug=True,exit_on_error=False)
  if err or not re.match("^\d+$",out): return -1
  return int(out)

def check_dead_transfers(threads, info, progress_check=600, init_transfer_wait=600):
  thds_done = False
  for t in threads:
    if not t.is_alive():
      thds_done = True
      continue
    lfn = t.name
    pcheck = int(time())-info[lfn][0]
    if pcheck<init_transfer_wait: continue
    pcheck = int((pcheck-init_transfer_wait)/progress_check)
    if pcheck>info[lfn][1]:
      info[lfn][1]=pcheck
      mtime = getmtime(info[lfn][3])
      err, out = run_cmd("grep '\[ *[1-9][0-9]*\%%\]' %s | tail -1" % info[lfn][3],debug=False,exit_on_error=False)
      out = re.sub("^.*\[","",re.sub("\].*$","", out.split("\n")[-1].split("\r")[-1]))
      if mtime!=info[lfn][2]:
        info[lfn][2]=mtime
        print("  In progress: %s %s" % (lfn,out))
      else:
        print("  Transfer stopped: %s %s" % (lfn, out))
        kill_xrootd(lfn)
        thds_done = True
  return thds_done

def copy_lfns_to_eos(eos_lfns):
  threads = []
  all_logs = {}
  logdir = "logs"
  run_cmd("rm -rf %s && mkdir -p %s" % (logdir , logdir))
  job_monitor = {}
  already_done =0
  total_lfns = len(eos_lfns)
  eos_lfns_to_copy = []
  for lfn in eos_lfns:
    if not lfn.endswith('.root'):
      already_done += 1
      print("IGNORE (%s/%s): %s" % (already_done, total_lfns, lfn))
      continue
    eos_file = "%s%s" % (eos_base, lfn)
    if eos_exists(eos_file) or (eos_exists(eos_file+".unused") and eos_rename(eos_file+".unused", eos_file)):
      already_done += 1
      print("OK (%s/%s): %s" % (already_done, total_lfns, lfn))
    elif opts.dryRun:
      print("DryRun: Copy %s -> %s" % (lfn, eos_file))
      continue
    else:
      eos_lfns_to_copy.append(lfn)
  for lfn in eos_lfns_to_copy:
    eos_file = "%s%s" % (eos_base, lfn)
    while True:
      threads = get_alive_threads(threads)
      if(len(threads) < opts.jobs):
        log_file=logdir+"/"+sha256(lfn.encode()).hexdigest()+".log"
        all_logs[log_file]=lfn
        print("Copy (%s/%s): %s" % (already_done+len(all_logs), total_lfns, lfn))
        t = Thread(name=lfn,target=copy_to_eos, args=(lfn, log_file))
        job_monitor[lfn]=[int(time()), 0, 0,log_file]
        t.start()
        threads.append(t)
        break
      elif not check_dead_transfers(threads, job_monitor):
        sleep(10)
  while len(threads)>0:
    sleep(10)
    threads = get_alive_threads(threads)
    check_dead_transfers(threads, job_monitor)
  total_failed = 0
  total_copied = 0
  for log in all_logs:
    lfn = all_logs[log]
    err, out = run_cmd("cat %s" % log,debug=False)
    err, out = getstatusoutput("grep '^ALL_OK$' %s | wc -l" % log)
    if out=="0":
      total_failed+=1
      print("FAIL (%s/%s): %s" % (already_done+total_copied+total_failed, total_lfns, lfn))
      err, out = getstatusoutput("cat %s" % log)
      print(out)
      print("###################################")
    else:
      total_copied += 1
      print("OK (%s/%s): %s" % (already_done+total_copied+total_failed, total_lfns, lfn))
  run_cmd("rm -rf %s" % logdir)
  print("Total LFNs:        %s" % total_lfns)
  print("Already available: %s" % already_done)
  print("Newly fetched:     %s" % total_copied)
  print("Error:             %s" % total_failed)
  return total_failed==0

if __name__ == "__main__":
  from optparse import OptionParser  
  parser = OptionParser(usage="%prog ")
  parser.add_option("-r", "--redirector",   dest="redirector",  help="Xroot reditrector",   type=str, default="root://cms-xrd-global.cern.ch")
  parser.add_option("-n", "--dry-run",      dest="dryRun",  action="store_true", help="Do not actually download the files", default=False)
  parser.add_option("-f", "--file-per-das", dest="files_per_das",   help="Number of files per das query need to be copy to EOS",  type=int, default=1)
  parser.add_option("-j", "--jobs",         dest="jobs",     help="Parallel jobs to run",   type=int, default=4)
  parser.add_option("-d", "--days",         dest="days",    help="Files access in last n days via kibana",   type=int, default=7)
  opts, args = parser.parse_args()
  
  all_OK = copy_lfns_to_eos(get_lfns_for_cmsbuild_eos(opts.files_per_das, opts.days))
  if not all_OK: exit(1)
  exit(0)

