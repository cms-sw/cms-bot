#!/usr/bin/env python
from hashlib import sha1
import os, sys,json , re , datetime
from os import getenv
from os.path import exists
from time import strftime , strptime
from socket import gethostname
from es_utils import send_payload
import xml.etree.ElementTree as ET

def es_parse_jobreport(payload,logFile):
  xmlFile = "/".join(logFile.split('/')[:-1]) + "/JobReport"+logFile.split('/')[-1].split("_")[0][-1]+".xml"
  if not os.path.exists(xmlFile): return payload
  payload['jobreport'] = xmlFile.replace('/data/sdt/' , 'https://cmssdt.cern.ch/SDT/cgi-bin/')
  tree = ET.parse(xmlFile)
  root = tree.getroot()
  events_read = []
  total_events = []
  for i in root.getiterator("EventsRead") : events_read.append(i.text)
  for i in root.getiterator("TotalEvents") : total_events.append(i.text)
  payload["events_read"] = max(events_read)
  payload["total_events"] = max(total_events)
  reports_p = root.getiterator('PerformanceReport')
  for i in reports_p:
    summaries = i.getiterator("PerformanceSummary")
    for j in summaries:
      if j.get("Metric") == "SystemMemory" or j.get("Metric") == "StorageStatistics":
        continue
      if j.get("Metric") == "ApplicationMemory":
        metrics_list = j.getchildren()
        for i in metrics_list:
          name=i.get("Name")
          if name in ["AverageGrowthRateRss", "AverageGrowthRateVsize", "PeakValueVsize"]:
            payload[name] = i.get("Value")
      elif j.get("Metric") == "Timing":
        metrics_list = j.getchildren()
        for i in metrics_list:
          payload[i.get("Name")] = i.get("Value")
  return payload

def es_parse_log(logFile):
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
  index = "ib-matrix-" + week
  document = "runTheMatrix-data"
  id = sha1(release + architecture + workflow + str(step)).hexdigest()
  payload["workflow"] = workflow
  payload["release"] = release
  payload["architecture"] = architecture
  payload["step"] = step
  payload["hostname"] = gethostname()
  payload["@timestamp"] = timestp
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
  try:
    payload = es_parse_jobreport(payload,logFile)
  except Exception, e
    print e
  send_payload(index,document,id,json.dumps(payload))
