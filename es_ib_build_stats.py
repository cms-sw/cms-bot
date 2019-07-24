#!/usr/bin/env python
from __future__ import print_function
import re, json, sys
from datetime import datetime
from os.path import getmtime, exists
from _py2with3compatibility import run_cmd
from es_utils import send_payload
from hashlib import sha1
from cmsutils import cmsswIB2Week

ReDate = re.compile("DATE=[A-Z][a-z]{2}\s+([A-Z][a-z]{2}\s+[0-9]{1,2}\s+\d\d:\d\d:\d\d\s+)[A-Z]{3,4}\s+(\d\d\d\d)")
ReUpload = re.compile("^.*sync-back\s+upload\s+.*")
ReRel = re.compile("^[+]\s+RELEASE_FORMAT=(CMSSW_.+)")
ReArch = re.compile("^[+]\s+ARCHITECTURE=(.+)")
ReType = re.compile(".+specs-only\s+build\s+(cmssw-patch).*")
ReFinish = re.compile("Finished:\s+[A-Z]+")

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
        if "ABORTED" in line: return True
        break
      if ReUpload.match(line):
        upload=True
        print("Upload: ",stime,line)
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
  print("FINISHED: ",finished,rel, arch,uploadTime,jstart,upload,patch)
  if not rel or not arch or not finished: return finished
  urlx = logFile.split("/")
  url = "https://cmssdt.cern.ch/jenkins/job/build-any-ib/"+logFile.split("/")[-2]+"/console"
  timestp  = getmtime(logFile)
  ttime=0
  if jend and jstart:
    dtime = jend - jstart
    ttime = dtime.seconds 
  print(ttime, uploadTime, rel, arch, patch, url)
  payload = {}
  payload["release"] = rel
  payload["architecture"] = arch
  payload["total_time"] = ttime
  payload["upload_time"] = uploadTime
  payload["patch"] = patch
  payload["@timestamp"] = int(timestp*1000)
  payload["url"]=url
  week, rel_sec = cmsswIB2Week(rel)
  print(payload)
  id = sha1(rel + arch).hexdigest()
  send_payload("jenkins-ibs-"+week,"timings",id,json.dumps(payload))
  return finished
    
force=False
try:
  x=sys.argv[1]
  force=True
except:
  pass
err, logs = run_cmd("find /build/jobs/build-any-ib/builds -follow -maxdepth 2 -mindepth 2 -name log -type f")
logs = logs.split('\n')
for logFile in logs:
  flagFile = logFile + '.ib-build'
  if force or (not exists(flagFile)):
    print("Processing ",logFile)
    done = True
    if re.match("^.+/builds/\d+/log$",logFile):
      done = process_build_any_ib(logFile)
    if done: run_cmd('touch "' + flagFile + '"')
