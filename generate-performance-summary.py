#!/usr/bin/env python
from __future__ import print_function
from _py2with3compatibility import run_cmd
from os.path import dirname
from xml.sax import parseString, ContentHandler
import argparse
import re
from sys import exit
import sys
import time
import pickle
import struct
import socket
from datetime import date, timedelta

CARBON_SERVER = '0.0.0.0'
CARBON_PORT = 2004

class JobReportHandler(ContentHandler):
  def __init__(self, what, step, architecture, release, workflow, timestamp):
    ContentHandler.__init__(self)
    self.counters = dict((k, "") for k in what)
    self.step = step
    self.architecture = architecture
    self.release = release
    self.workflow = workflow
    self.timestamp = timestamp 
    self.metrics = []

  def startElement(self, name, attrs):
    if name != "Metric":
      return
    
    if not attrs["Name"] in self.counters:
      return
    if "nan" in attrs["Value"]:
      return

    path = ".".join(["IBRelVals", self.architecture, self.release, self.workflow, self.step, attrs["Name"]])
    value = attrs["Value"]
    timestamp = time.mktime(self.timestamp)
    self.metrics.append((path, (timestamp, value)))
    self.counters[attrs["Name"]] = attrs["Value"]

class SchemaDumper(ContentHandler):
  def __init__(self, schema):
    ContentHandler.__init__(self)
    self.schema = schema

  def startElement(self, name, attrs):
    if name != "Metric":
      return
    self.schema.add(attrs["Name"])

IB_BASE_DIR="/afs/cern.ch/cms/sw/ReleaseCandidates"

def chunks(l, n):
  for i in range(0, len(l), n):
    yield l[i:i+n]

def format(s, **kwds):
  return s % kwds

# 100 metrics at the time
def sendMetrics(metrics, server, port):
  for l in chunks(metrics, 100):
    payload = pickle.dumps(l)
    print(len(payload))
    header = struct.pack("!L", len(payload))
    message = header + payload
    sock = socket.socket()
    sock.connect((server, port))
    sock.sendall(message)
    sock.close()
    time.sleep(0.5)

def calculateFileSizeMetrics(release, architecture, timestamp, fullRelease, args):
  timestamp = time.mktime(timestamp)
  cmd = format("find %(base)s/vol*/%(architecture)s/cms/cmssw*/%(fullRelease)s/lib/%(architecture)s -name '*.so' -exec wc -c {} \; | sed -e 's|/.*/||;s|[.]so||'",
               base=IB_BASE_DIR,
               releasePath=releasePath,
               fullRelease=fullRelease,
               architecture=architecture)
  error, out = run_cmd(format(cmd))
  if error:
    return
  if not out.strip():
    return
  metrics = []
  for line in out.split("\n"):
    size, library = line.split(" ", 1)
    metric = ".".join(["IBStats", architecture, release, library, "FileSize"])
    metrics.append((metric, (timestamp, size)))
  sendMetrics(metrics, args.server, args.port)

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description='Extract plot data from IB job reports')
  parser.add_argument('--base-dir', dest='baseDir', default=IB_BASE_DIR,
                      help='Where the logs are located.')
  parser.add_argument('--server', dest='server', default=CARBON_SERVER,
                      help='Where the logs are located.')
  parser.add_argument('--port', dest='port', default=CARBON_PORT,
                      help='Where the logs are located.')
  parser.add_argument('--filter-release', dest='filterRelease', default=".*",
                      help='regexp to filter releases')
  parser.add_argument('--filter-workflows', dest='filterWorkflows', default=".*",
                      help='regexp to filter releases')
  parser.add_argument('--days', dest="days", default=7, type=int, help="days to go into the past.")
  parser.add_argument('what', metavar='KEYS', type=str, nargs='*',
                      help='What to dump from the logs')
  args = parser.parse_args()

  print("Parsing files", file=sys.stderr)
  cmd = "find %s/slc* -name 'pyRelValMatrixLogs.zip' | sort -r" % IB_BASE_DIR
  print(cmd)
  error, files = run_cmd(cmd)
  files = [x for x in files.split("\n") if x]
  schema = set()
  beginning = (date.today() - timedelta(args.days)).timetuple()
  for f in files:
    print(f, file=sys.stderr)
    releasePath = dirname(f)
    architecture = re.sub(".*/((slc|osx|fc)[^/]*)/.*", "\\1", f)
    fullRelease = re.sub(".*/(CMSSW_[^/]*)/.*", "\\1", f)
    release = re.sub(".*/(CMSSW_[^/]*)/.*", "\\1", f)
    # Note for a future maintainer, remember to fix it by year 2100.
    date = re.sub(".*/CMSSW_[^/]*(20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]-[0-2][0-9][0-9][0-9]).*", "\\1", f)
    release = release.replace(date,"").strip("_")
    timestamp = time.strptime(date, "%Y-%m-%d-%H%M")
    if timestamp < beginning:
      continue
    if not re.match(args.filterRelease, release):
      continue
    error, reports = run_cmd("unzip -l %s | grep JobReport | awk '{print $4}'" % f)
    calculateFileSizeMetrics(release, architecture, timestamp, fullRelease, args)
    
    metrics = []
    for r in [x for x in reports.split("\n") if x]:
      cmd = "unzip -p %s %s" % (f, r)
      error, report = run_cmd(cmd)
      workflow = re.sub("^([^/]*).*", "\\1", r).replace(".","_")
      if not re.match(args.filterWorkflows, workflow):
        continue
      step = re.sub(".*JobReport([0-9]).*", "step\\1", r)
      if not args.what:
        handler = SchemaDumper(schema)
      else:
        handler = JobReportHandler(args.what, step, architecture, release, workflow, timestamp)
      try:
        parseString(report, handler)
      except:
        continue
      metrics += handler.metrics
      if schema:
        print("\n".join(sorted(schema)))
        exit(0)
    if not len(metrics):
      continue
    print("Sending %s metrics." % len(metrics))
    sendMetrics(metrics, args.server, args.port)
