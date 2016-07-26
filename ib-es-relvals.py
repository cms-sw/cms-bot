#!/usr/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os.path import exists, dirname
from time import strftime , strptime
from es_utils import send_payload
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
  dataset = {"type" : "relvals", "name" : "%s/%s" % (workflow, step), "ds_block" : "", "ds_status" : "", "ds_owner" : "", "ds-files" : "", "at_cern" : ""}
  dataset["release"]=release
  dataset["architecture"]=architecture
  dataset["@timestamp"]=timestp

  datasets=[]
  lines = file(logFile).read()
  for l in lines.split("\n"):
    if not " Initiating request to open file " in l: continue
    try:
      rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
      if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
    except: pass
  for ds in datasets:
    ds_items = ds.split("?",1)
    ds_items.append("")
    dataset["protocol"]=ds_items[0].split("/store/",1)[0]
    dataset["protocol_opts"]=ds_items[1]
    dataset["lfn"]="/store/"+ds_items[0].split("/store/",1)[1]
    idx = sha1(id + ds).hexdigest()
    send_payload("ib-dataset-"+week,"relvals-dataset",idx,json.dumps(dataset))


logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'pyRelValMatrixLogs.zip'")
logs = logs[1].split('\n')
for logFile in logs:
  flagFile = logFile + '.checked'
  if not exists(flagFile+"x1"):
    utdir = dirname(logFile)
    print "Working on ",logFile
    try:
      err, utlogs = commands.getstatusoutput("cd %s; rm -rf MT; mkdir MT; cd MT; unzip ../pyRelValMatrixLogs.zip" % utdir)
      err, utlogs = commands.getstatusoutput("find %s/MT -name 'step*.log' -type f" % utdir)
      if not err:
        for utlog in utlogs.split("\n"):
          process_matrix_log(utlog)
        commands.getstatusoutput("touch %s" % flagFile)
    except Exception as e:
      print "ERROR:",e
    commands.getstatusoutput("rm -rf %s/MT" % utdir)

