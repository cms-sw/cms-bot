#!/bin/env python
from hashlib import sha1
import sys,json , re
from os import getenv
from os.path import exists
import dateutil.parser
from socket import gethostname
from es_utils import send_payload

def es_parse_log(logFile):
  payload = {}
  pathInfo = logFile.split('/')
  architecture = pathInfo[4]
  release = pathInfo[8]
  workflow = pathInfo[10].split('_')[0]
  step = pathInfo[11].split('_')[0]
  dat = re.findall('\d{4}-\d{2}-\d{2}',release)[0]
  week = dateutil.parser.parse(dat).strftime("%U")
  index = "ib-matrix-" + week
  document = "runTheMatrix-data"
  id = sha1(release + architecture + workflow + str(step)).hexdigest()
  payload["workflow"] = workflow
  payload["release"] = release
  payload["architecture"] = architecture
  payload["step"] = step
  payload["hostname"] = gethostname()
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
  send_flag = False
  if exception:
    payload["exception"] = exception
    send_flag = True
  if errors:
    payload["errors"] = errors
    send_flag = True
  if (send_flag):
    send_payload(index,document,id,json.dumps(payload))
  else:
    print "nothing to send , no errors or exceptions found"
