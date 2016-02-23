#!/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os import getenv
from os.path import exists
from time import strftime , strptime
from socket import gethostname
from es_utils import send_payload

def es_parse_log(logFile):
  t = os.path.getmtime(logFile)
  timestp = datetime.datetime.fromtimestamp(int(t)).strftime('%Y-%m-%d %H:%M:%S')
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  workflow = pathInfo[10].split('_')[0]
  step = pathInfo[11].split('_')[0]
  dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  week = strftime("%U",strptime(dat,"%Y-%m-%d"))
  index = "ib-matrix-" + week
  document = "runTheMatrix-data"
  id = sha1(release + architecture + workflow + str(step)).hexdigest()
  payload["workflow"] = workflow
  payload["release"] = release
  payload["architecture"] = architecture
  payload["step"] = step
  payload["hostname"] = gethostname()
  payload["tstamp"] = timestp
  exception = ""
  error = ""
  errors = []
  inException = False
  inError = False
  if exists(logFile):
    lines = file(logFile).read()
    payload["url"] = logFile.replace('/data/sdt/' , 'https://cmssdt.cern.ch/SDT/cgi-bin/')
    for l in lines.split("\n"):
      if l.startswith("----- Begin Fatal Exception"):
        inException = True
        continue
      if l.startswith("----- End Fatal Exception"):
        inException = False
        continue
      if l.startswith("%MSG-e"):
        inError = True
        error = l
        error_kind = re.split(" [0-9a-zA-Z-]* [0-9:]{8} CET", error)[0].replace("%MSG-e ", "")
        continue
      if inError == True and l.startswith("%MSG"):
        inError = False
        errors.append({"error": error, "kind": error_kind})
        error = ""
        error_kind = ""
        continue
      if inException:
        exception += l + "\n"
      if inError:
        error += l + "\n"
  if exception:
    payload["exception"] = exception
  if errors:
    payload["errors"] = errors
  send_payload(index,document,id,json.dumps(payload))
