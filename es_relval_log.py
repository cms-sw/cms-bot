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
  payload['jobreport'] = '/'.join(payload["url"].split('/')[:-1])+'/'+xmlFile.split('/')[-1]
  tree = ET.parse(xmlFile)
  root = tree.getroot()
  events_read = []
  total_events = []
  for i in root.getiterator("EventsRead") : events_read.append(i.text)
  for i in root.getiterator("TotalEvents") : total_events.append(i.text)
  if events_read: payload["events_read"] = max(events_read)
  if total_events: payload["total_events"] = max(total_events)
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
            val = i.get("Value")
            if 'nan' in val: val=''
            payload[name] = val
      elif j.get("Metric") == "Timing":
        metrics_list = j.getchildren()
        for i in metrics_list:
          val = i.get("Value")
          if 'nan' in val:
            val=''
          elif 'e' in val:
            val=float(val)
          payload[i.get("Name")] = val
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
  payload["@timestamp"] = timestp
  hostFile = "/".join(logFile.split('/')[:-1]) + "/hostname"
  if os.path.exists (hostFile):
    with open(hostFile,'r') as hname:
      payload["hostname"] = hname.readlines()[0].strip()
  exception = ""
  error = ""
  errors = []
  inException = False
  inError = False
  if exists(logFile):
    lines = file(logFile).read()
    payload["url"] = 'https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/'+pathInfo[4]+'/'+pathInfo[8]+'/pyRelValMatrixLogs/run/'+pathInfo[-2]+'/'+pathInfo[-1]
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
  except Exception, e:
    print e
  print "sending data for ",logFile
  send_payload(index,document,id,json.dumps(payload))

if __name__ == "__main__":
  print "Processing ",sys.argv[1]
  es_parse_log(sys.argv[1])
