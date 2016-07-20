#!/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os import getenv
from os.path import exists, dirname
from time import strftime , strptime
from es_utils import send_payload
import commands

def send_unittest_dataset(datasets, payload, id, index, doc):
  for ds in datasets:
    payload["file"]=ds
    print payload, index, doc
    send_payload(index, doc, sha1(id + ds).hexdigest(), json.dumps(payload))

def process_unittest_log(logFile):
  t = os.path.getmtime(logFile)
  timestp = int(t*1000)
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  week = strftime("%U",strptime(dat,"%Y-%m-%d"))
  package = pathInfo[-3]+"/"+ pathInfo[-2]
  utname = None
  datasets = []
  payload = {"type" : "unittest"}
  payload["release"]=release
  payload["architecture"]=architecture
  payload["@timestamp"]=timestp
  id = None
  for l in file(logFile).read().split("\n"):
    if l.startswith('===== Test "') and l.endswith('" ===='):
      if utname: send_unittest_dataset(datasets, payload, id, "ib-dataset-"+week, "unittest-dataset")
      datasets = []
      utname = l.split('"')[1]
      payload["name"] = "%s/%s" % (package, utname)
      id = sha1(release + architecture + package + str(utname)).hexdigest()
    elif " Initiating request to open file " in l:
      try:
        rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
        if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
      except: pass
  if datasets: send_unittest_dataset(datasets, payload, id, "ib-dataset-"+week,"unittest-dataset")
  return

def process_addon_log(logFile):
  t = os.path.getmtime(logFile)
  timestp = int(t*1000)
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  week = strftime("%U",strptime(dat,"%Y-%m-%d"))
  datasets = []
  payload = {"type" : "addon"}
  payload["release"]=release
  payload["architecture"]=architecture
  payload["@timestamp"]=timestp
  payload["name"] = pathInfo[-1].split("-")[1].split("_cmsRun_")[0].split("_cmsDriver.py_")[0]
  id = sha1(release + architecture + "addon" + payload["name"]).hexdigest()
  for l in file(logFile).read().split("\n"):
    if " Initiating request to open file " in l:
      try:
        rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
        if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
      except: pass
  send_unittest_dataset(datasets, payload, id, "ib-dataset-"+week,"addon-dataset")
  return

def process_ib_utests(logFile):
  t = os.path.getmtime(logFile)
  timestp = datetime.datetime.fromtimestamp(int(t)).strftime('%Y-%m-%d %H:%M:%S')
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  #dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  index = "ibs"
  document = "unittests"
  payload["release"] = release
  payload["architecture"] = architecture
  payload["@timestamp"] = timestp

  if exists(logFile):
    with open(logFile) as f:
      try:
        it = iter(f)
        line = it.next()
        while '--------' not in line:
          line = it.next()
        while True:
          line=it.next().strip()
          if ":" in line:
            pkg = line.split(':')[0].strip()
            payload["url"] = 'https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/'+ architecture +'/'+ release +'/unitTestLogs/' + pkg
            line = it.next().strip()
            while ':' not in line:
              if "had ERRORS" in line:
                payload["status"] = 1
              else:
                payload["status"] = 0
              utest= line.split(' ')[0]
              payload["package"] = pkg
              payload["name"] = utest
              id = sha1(release + architecture + utest).hexdigest()
              send_payload(index,document,id,json.dumps(payload))
              line = it.next().strip()
      except Exception as e:
        print "File processed:", e
  else:
    print "Invalid File Path"

#get log files
logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTests-summary.log'")
logs = logs[1].split('\n')
#process log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not os.path.exists(flagFile):
    print "Working on ",logFile
    process_ib_utests(logFile)
    os.system('touch "' + flagFile + '"')

logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTestLogs.zip'")
logs = logs[1].split('\n')
#process zip log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not os.path.exists(flagFile):
    utdir = dirname(logFile)
    print "Working on ",logFile
    try:
      err, utlogs = commands.getstatusoutput("cd %s; rm -rf UT; mkdir UT; cd UT; unzip ../unitTestLogs.zip" % utdir)
      err, utlogs = commands.getstatusoutput("find %s/UT -name 'unitTest.log' -type f" % utdir)
      if not err:
        for utlog in utlogs.split("\n"):
          process_unittest_log(utlog)
        commands.getstatusoutput("touch %s" % flagFile)
    except Exception as e:
      print "ERROR:",e
    commands.getstatusoutput("rm -rf %s/UT" % utdir)

logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'addOnTests.zip'")
logs = logs[1].split('\n')
#process zip log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not os.path.exists(flagFile):
    utdir = dirname(logFile)
    print "Working on ",logFile
    try:
      err, utlogs = commands.getstatusoutput("cd %s; rm -rf AO; mkdir AO; cd AO; unzip ../addOnTests.zip" % utdir)
      err, utlogs = commands.getstatusoutput("find %s/AO -name '*.log' -type f" % utdir)
      if not err:
        for utlog in utlogs.split("\n"):
          process_addon_log(utlog)
        commands.getstatusoutput("touch %s" % flagFile)
    except Exception as e:
      print "ERROR:",e
    commands.getstatusoutput("rm -rf %s/AO" % utdir)

