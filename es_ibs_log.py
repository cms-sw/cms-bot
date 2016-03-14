#!/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os import getenv
from os.path import exists
from time import strftime , strptime
from es_utils import send_payload
import commands

def process_ib_utests(logFile):
  t = os.path.getmtime(logFile)
  timestp = datetime.datetime.fromtimestamp(int(t)).strftime('%Y-%m-%d %H:%M:%S')
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[0]
  release = pathInfo[4]
  #dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  index = "ibs"
  document = "unittests"
  payload["release"] = release
  payload["architecture"] = architecture
  payload["@timestamp"] = timestp
  payload["url"] = 'https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/'+ architecture +'/'+ release +'/unitTestLogs/CommonTools/Utils'

  if exists(logFile):
    with open(logFile) as f:
      try:
        it = iter(f)
        line = it.next()
        while '--------' not in line:
          line = it.next()
        while True:
          line=it.next()
          if ":" in line:
            pkg = line.split(':')[0].strip()
            line = it.next()
            while ':' not in line:
              if "had ERRORS" in line:
                payload["status"] = 0
              else:
                payload["status"] = 1
              utest= line.split(' ')[-2]
              payload["pakage"] = pkg
              payloaf["unit_test"] = utest
              id = sha1(release + architecture + pkg + utest).hexdigest()
              send_payload(index,document,id,json.dumps(payload))
              print "sent"
              line = it.next()
      except:
        print "File processed"
  else:
    print "Invalid File Path"

#get log files
logs = commands.getstatusoutput("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTests-summary.log'")
logs = logs[1].split('\n')
#process log files
for logFile in logs:
  flagFile = logFile + '.checked'
  if not os.path.exists(flagFile):
    process_ib_utests(logFile)
    os.system('touch "' + flagFile + '"')
