#!/usr/bin/env python
import sys
import re
from datetime import datetime
from os.path import getmtime, exists
from commands import getstatusoutput
from es_utils import send_payload
from hashlib import sha1

ReDate = re.compile("DATE=[A-Z][a-z]{2}\s+([A-Z][a-z]{2}\s+\d\d\s+\d\d:\d\d:\d\d\s+)[A-Z]{3}\s+(\d\d\d\d)")
ReUpload = re.compile("^[+]{2}\s+type=upload")
ReRel = re.compile("^[+]\s+RELEASE_FORMAT=(CMSSW_.+)")
ReArch = re.compile("^[+]\s+ARCHITECTURE=(.+)")
ReType = re.compile(".+specs-only\s+build\s+(cmssw-patch).*")
ReFinish = re.compile("Finished:\s[A-Z]+")

def process_build_any_ib(logFile):
  rel = ""
  arch = ""
  uploadTime=0
  stime=0
  upload=False
  jstart = 0
  jend=0
  patch = 0
  finished = False
  with open(logFile) as f:
    for line in f:
      line = line.strip()
      
      if not jstart:
        m=ReDate.match(line)
        if m:
          jstart = datetime.strptime(m.group(1)+m.group(2), "%b %d %H:%M:%S %Y")
        continue
      if not arch:
        m=ReArch.match(line)
        if m: arch=m.group(1)
        continue
      if not rel:
        m=ReRel.match(line)
        if m: rel=m.group(1)
        continue
      if ReFinish.match(line):
        finished = True
        break
      if ReUpload.match(line):
        upload=True
        continue
      if ReType.match(line): patch=1
      m=ReDate.match(line)
      if not m: continue
      xtime = datetime.strptime(m.group(1)+m.group(2), "%b %d %H:%M:%S %Y")
      jend = xtime
      if not upload:
        stime = xtime
      else:
        upload=False
        dtime = xtime - stime 
        uploadTime += dtime.seconds
  print "FINISHED: ",finished
  if not rel or not arch or not finished: return False
  urlx = logFile.split("/")
  url = "https://cmssdt.cern.ch/jenkins/job/build-any-ib/"+logFile.split("/")[-2]+"/console"
  timestp  = getmtime(logFile)
  ttime = jend - jstart
  print ttime.seconds, uploadTime, rel, arch, patch, url
  payload = {}
  payload["release"] = rel
  payload["architecture"] = arch
  payload["total_time"] = ttime.seconds
  payload["upload_time"] = uploadTime
  payload["patch"] = patch
  payload["@timestamp"] = timestp
  payload["url"]=url
  id = sha1(rel + arch).hexdigest()
  send_payload("jenkins","build-any-ib",id,json.dumps(payload))
    
err, logs = getstatusoutput("find /build/jobs/build-any-ib/builds -maxdepth 2 -mindepth 2 -name log -type f")
logs = logs.split('\n')
for logFile in logs:
  flagFile = logFile + '.ib-stats'
  if not exists(flagFile):
    print "Processing ",logFile
    done = True
    if re.match("^.+/builds/\d+/log$",logFile):
      done = process_build_any_ib(logFile)
    if done: getstatusoutput('touch "' + flagFile + '"')
