#!/usr/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os.path import exists, dirname
from time import strftime , strptime, sleep
from es_utils import send_payload
from threading import Thread
from sys import argv
import commands

def process_matrix_log(logFile):
  t = os.path.getmtime(logFile)
  timestp = int(t*1000)
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  workflow = pathInfo[10].split('_')[0]
  step = pathInfo[11].split('_')[0]
  dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  week = strftime("%U",strptime(dat,"%Y-%m-%d"))
  id = sha1(release + architecture + workflow + str(step)).hexdigest()
  dataset = {"type" : "relvals", "name" : "%s/%s" % (workflow, step), "ds_block" : "", "ds_status" : "", "ds_owner" : "", "ds_files" : "", "at_cern" : ""}
  dataset["release"]=release
  dataset["architecture"]=architecture
  dataset["@timestamp"]=timestp

  datasets=[]
  lines = file(logFile).read()
  for l in lines.split("\n"):
    if not " Initiating request to open file " in l: continue
    rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
    if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
  for ds in datasets:
    ds_items = ds.split("?",1)
    ds_items.append("")
    dataset["protocol"]=ds_items[0].split("/store/",1)[0]
    dataset["protocol_opts"]=ds_items[1]
    dataset["lfn"]="/store/"+ds_items[0].split("/store/",1)[1]
    idx = sha1(id + ds).hexdigest()
    send_payload("ib-dataset-"+week,"relvals-dataset",idx,json.dumps(dataset))
  return

def process_log(logFile):
  flagFile = logFile + '.checked.new'
  utdir = dirname(logFile)
  commands.getstatusoutput("cd %s; rm -rf XMT MT" % utdir)
  if not exists(flagFile):
    err, utlogs = commands.getstatusoutput("cd %s; mkdir XMT; cd XMT; unzip ../pyRelValMatrixLogs.zip" % utdir)
    err, utlogs = commands.getstatusoutput("find %s/XMT -mindepth 2 -name 'step*_*.log' -type f" % utdir)
    if not err:
      err_msg = ""
      for log in utlogs.split("\n"):
        try:
          process_matrix_log(log)
        except Exception as e:
          err_msg = "ERROR:"+str(e)
          break
      if not err_msg:
        print "DONE  %s" % logFile
        commands.getstatusoutput("touch %s" % flagFile)
      else:
        print "FAIL  %s\n%s" % (logFile, err_msg)
    commands.getstatusoutput("rm -rf %s/XMT" % utdir)
  else: print "SKIP  %s" % logFile

logs = argv[1:]
if len(logs)==0:
  logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'pyRelValMatrixLogs.zip'")
  logs = logs[1].split('\n')

threads = []
while(logs):
  threads = [t for t in threads if t.is_alive()]
  if(len(threads) < 4):
    try:
      t = Thread(target=process_log, args=(logs.pop(),))
      t.start()
      threads.append(t)
    except Exception:
      print "Error: %s" % str(exc_info()[1])
  else:
    sleep(0.1)
for t in threads: t.join()

