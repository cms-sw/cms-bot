#!/bin/env python
from __future__ import print_function
from hashlib import sha1
import os, json,  datetime, sys
from glob import glob
from os.path import exists, dirname, getmtime
from es_utils import send_payload
from _py2with3compatibility import run_cmd
from cmsutils import cmsswIB2Week
from logreaderUtils import transform_and_write_config_file, add_exception_to_config, ResultTypeEnum
import traceback

def send_unittest_dataset(datasets, payload, id, index, doc):
  for ds in datasets:
    print("Processing ",ds)
    if not 'root://' in ds: continue
    ds_items = ds.split("?",1)
    ds_items.append("")
    ibeos = "/store/user/cmsbuild"
    if ibeos in ds_items[0]: ds_items[0] = ds_items[0].replace(ibeos,"")
    else: ibeos=""
    payload["protocol"]=ds_items[0].split("/store/",1)[0]+ibeos
    payload["protocol_opts"]=ds_items[1]
    payload["lfn"]="/store/"+ds_items[0].split("/store/",1)[1].strip()
    print ("Sending",index, doc, sha1(id + ds).hexdigest(), json.dumps(payload))
    send_payload(index, doc, sha1(id + ds).hexdigest(), json.dumps(payload))

def process_unittest_log(logFile):
  t = getmtime(logFile)
  timestp = int(t*1000)
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  week, rel_sec  = cmsswIB2Week (release)
  package = pathInfo[-3]+"/"+ pathInfo[-2]
  payload = {"type" : "unittest"}
  payload["release"]=release
  payload["architecture"]=architecture
  payload["@timestamp"]=timestp
  config_list = []
  custom_rule_set = [
    {"str_to_match": "test (.*) had ERRORS", "name": "{0} failed", 'control_type': ResultTypeEnum.ISSUE },
    {"str_to_match": '===== Test "([^\s]+)" ====', "name": "{0}", 'control_type': ResultTypeEnum.TEST }
  ]
  with open(logFile) as f:
    utname = None
    datasets = []
    xid = None
    for index, l in enumerate(f):
      l = l.strip()
      config_list = add_exception_to_config(l,index,config_list,custom_rule_set)
      if l.startswith('===== Test "') and l.endswith('" ===='):
        if utname: send_unittest_dataset(datasets, payload, xid, "ib-dataset-"+week, "unittest-dataset")
        datasets = []
        utname = l.split('"')[1]
        payload["name"] = "%s/%s" % (package, utname)
        xid = sha1(release + architecture + package + str(utname)).hexdigest()
      elif " Initiating request to open file " in l:
        try:
          rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
          if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
        except Exception as e:
          print("ERROR: ",logFile,e)
          traceback.print_exc(file=sys.stdout)
    if datasets and xid:
      send_unittest_dataset(datasets, payload, xid, "ib-dataset-"+week,"unittest-dataset")
  transform_and_write_config_file(logFile + "-read_config", config_list)
  return

def process_addon_log(logFile):
  t = getmtime(logFile)
  timestp = int(t*1000)
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  week, rel_sec  = cmsswIB2Week (release)
  datasets = []
  payload = {"type" : "addon"}
  payload["release"]=release
  payload["architecture"]=architecture
  payload["@timestamp"]=timestp
  payload["name"] = pathInfo[-1].split("-")[1].split("_cmsRun_")[0].split("_cmsDriver.py_")[0]
  id = sha1(release + architecture + "addon" + payload["name"]).hexdigest()
  config_list = []
  with open(logFile) as f:
    for index, l in enumerate(f):
      l = l.strip()
      config_list = add_exception_to_config(l,index, config_list)
      if " Initiating request to open file " in l:
        try:
          rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
          if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
        except: pass
  send_unittest_dataset(datasets, payload, id, "ib-dataset-"+week,"addon-dataset")
  transform_and_write_config_file(logFile + "-read_config", config_list)
  return

def process_hlt_log(logFile):
  t = getmtime(logFile)
  timestp = int(t*1000)
  pathInfo = logFile.split('/')
  architecture = pathInfo[-2]
  release = pathInfo[-3]
  week, rel_sec  = cmsswIB2Week (release)
  datasets = []
  payload = {"type" : "hlt"}
  payload["release"]=release
  payload["architecture"]=architecture
  payload["@timestamp"]=timestp
  payload["name"] = pathInfo[-1][:-4]
  id = sha1(release + architecture + "hlt" + payload["name"]).hexdigest()
  with open(logFile) as f:
    for index, l in enumerate(f):
      l = l.strip()
      if " Initiating request to open file " in l:
        try:
          rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
          if (not "file:" in rootfile) and (not rootfile in datasets): datasets.append(rootfile)
        except: pass
  send_unittest_dataset(datasets, payload, id, "ib-dataset-"+week,"hlt-dataset")
  return

def process_ib_utests(logFile):
  t = getmtime(logFile)
  timestp = int(t*1000)
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  week, rel_sec  = cmsswIB2Week (release)
  index = "ibs-"+week
  document = "unittests"
  payload["release"] = release
  release_queue = "_".join(release.split("_", -1)[:-1]).split("_", 3)
  payload["release_queue"] = "_".join(release_queue[0:3])
  flavor = release_queue[-1]
  if flavor == 'X': flavor = 'DEFAULT'
  payload["flavor"] = flavor
  payload["architecture"] = architecture
  payload["@timestamp"] = timestp

  if exists(logFile):
    with open(logFile) as f:
      try:
        it = iter(f)
        line = next(it)
        while '--------' not in line:
          line = next(it)
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
              print("==> ", json.dumps(payload) + '\n')
              send_payload(index,document,id,json.dumps(payload))
              line = it.next().strip()
      except Exception as e:
        print("ERROR: File processed: %s" % e)
  else:
    print("Invalid File Path")

#get log files
logs = run_cmd("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTests-summary.log'")
logs = logs[1].split('\n')
#process log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not exists(flagFile):
    print("Working on ",logFile)
    process_ib_utests(logFile)
    os.system('touch "' + flagFile + '"')

logs = run_cmd("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTestLogs.zip'")
logs = logs[1].split('\n')
#process zip log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not exists(flagFile):
    utdir = dirname(logFile)
    print("Working on ",logFile)
    try:
      err, utlogs = run_cmd("cd %s; rm -rf UT; mkdir UT; cd UT; unzip ../unitTestLogs.zip" % utdir)
      err, utlogs = run_cmd("find %s/UT -name 'unitTest.log' -type f" % utdir)
      if not err:
        for utlog in utlogs.split("\n"):
          process_unittest_log(utlog)
        run_cmd("touch %s" % flagFile)
    except Exception as e:
        print("ERROR: ",logFile,e)
        traceback.print_exc(file=sys.stdout)
    run_cmd("cd %s/UT ; zip -r ../unitTestLogs.zip ." % utdir)
    run_cmd("rm -rf %s/UT" % utdir)

logs = run_cmd("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'addOnTests.zip'")
logs = logs[1].split('\n')
#process zip log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not exists(flagFile):
    utdir = dirname(logFile)
    print("Working on ",logFile)
    try:
      err, utlogs = run_cmd("cd %s; rm -rf AO; mkdir AO; cd AO; unzip ../addOnTests.zip" % utdir)
      err, utlogs = run_cmd("find %s/AO -name '*.log' -type f" % utdir)
      if not err:
        for utlog in utlogs.split("\n"):
          process_addon_log(utlog)
        run_cmd("touch %s" % flagFile)
    except Exception as e:
      print("ERROR:",e)
    run_cmd("cd %s/AO ; zip -r ../addOnTests.zip ." % utdir)
    run_cmd("rm -rf %s/AO" % utdir)

dirs = run_cmd("find /data/sdt/SDT/jenkins-artifacts/HLT-Validation -maxdepth 2 -mindepth 2 -type d")[1].split('\n')
for d in dirs:
  flagFile = d + '.checked'
  if exists(flagFile): continue
  for logFile in glob(d+"/*.log"):
    print("Working on ",logFile)
    try:
        process_hlt_log(logFile)
    except Exception as e:
      print("ERROR:",e)
  run_cmd("touch %s" % flagFile)
