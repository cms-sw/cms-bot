#!/usr/bin/env python3
import os, sys, json, socket, re, base64
from glob import glob
from optparse import OptionParser
from os.path import basename, join
from os import getenv
from time import strftime, localtime, strptime, sleep
from hashlib import sha1
from _py2with3compatibility import run_cmd, Request, urlopen, HTTPError

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.0"
SLEEP_CYCLE = 2 # seconds
TERM_CMD = "kill_reader"

def esReportPackages(results):
  # Silently exit if we cannot contact elasticsearch
  es_hostname = getenv("ES_HOSTNAME")
  es_auth = getenv("ES_AUTH")
  if not es_hostname and not es_auth:
    return

  url = "https://%s/_bulk" % (es_hostname)

  request = Request(url)
  if es_auth:
    base64string = base64.encodestring(es_auth).replace('\n', '')
    request.add_header("Authorization", "Basic %s" % base64string)
  request.get_method = lambda: 'POST'
  data = "\n".join(results) + "\n"
  try:
    result = urlopen(request, data=data)
  except  HTTPError as e:
    print(e)
    try:
      print(result.read())
    except:
      pass

if __name__ == "__main__":
  WORKSPACE = os.getenv("WORKSPACE", "./")
  WORK_DIR = join(WORKSPACE, "pkg_mon")
  SOURCE_DIR = join(os.getenv("CMSSW_BASE", "./"), "src")

  parser = OptionParser(usage="%prog [-f, -n]")
  parser.add_option("-f", "--force", dest="force", action="store_true",
                     help="Force pushing", default=False)
  parser.add_option("-n", "--dry-run", dest="dryrun", action="store_true",
                     help="Do not push files to server", default=False)
  opts, args = parser.parse_args()

  CMSSW_VERSION = os.getenv("CMSSW_VERSION", "unknown")
  SCRAM_ARCH = os.getenv("SCRAM_ARCH", "unknown")
  INDEX_NAME = strftime("ib-scram-stats-%Y.%m.%d")
  defaults = { "hostname": socket.gethostname(),
               "scram_arch": SCRAM_ARCH,
               "cmssw_version": CMSSW_VERSION,
             }
  print("Workspace: " + WORKSPACE + " workdir: " + WORK_DIR)
  while(True):
      sleep(SLEEP_CYCLE)
      print("New cycle, finding timestamps to send.")
      timestamps = sorted([int(basename(x).split("_")[1].split("-")[0])
                            for x in glob(join(WORK_DIR, "st*"))])
      job_done = os.path.isfile(join(WORK_DIR, TERM_CMD))
      if (len(timestamps) < 2 and not opts.force and not job_done):
        continue
      results = []
      removables = []
      RE_FILE = "(start|stop)_([0-9]+)-(.*)"
      pushables = [basename(f).replace(":", "/") for f in glob(join(WORK_DIR, "st*"))]
      info = [re.match(RE_FILE, f).groups() for f in pushables]
      m = re.match("(.*)_(20[0-9]{2}-[0-9]{2}-[0-9]{2}-[0-9]{4})", CMSSW_VERSION)
      if m:
        defaults["cmssw_queue"] = m.group(1)
        defaults["@timestamp"] = strftime("%Y-%m-%dT%H:%M:00.0",
                                          strptime(m.group(2), "%Y-%m-%d-%H%M"))
      starts = dict([(x[2], int(x[1])) for x in info if x[0] == "start"])
      stops = dict([(x[2], int(x[1])) for x in info if x[0] == "stop"])
      packages = set(x[2] for x in info)
      for x in packages:
        h = sha1((x + SCRAM_ARCH + CMSSW_VERSION).encode()).hexdigest()
        header = { "index" : { "_index" : INDEX_NAME,
                               "_type" : "cmssw_pkg_times",
                               "_id": h}
                 }
        data = {"package": x}
        data.update(defaults)
        startTime = starts.get(x, None)
        stopTime = stops.get(x, None)
        if startTime:
          data["start"] = strftime(TIME_FORMAT, localtime(startTime))
          if job_done:
              removables.append(x.replace("/",":"))
        if stopTime:
          data["stop"] = strftime(TIME_FORMAT, localtime(stopTime))
          if job_done:
              removables.append(x.replace("/",":"))
        if startTime and stopTime:
          data["diff"] = stopTime - startTime
          removables.append(x.replace("/", ":"))
        results += [json.dumps(header), json.dumps(data)]
    
      # Actually do the push to ES.
      if opts.dryrun:
        print("Dry run specified, what I would have sent:\n" + "\n".join(results))
      else:
        esReportPackages(results)
    
      for x in removables:
        cmd = "find %s -name \"*%s\" -delete" % (WORK_DIR, x)
        err, out = run_cmd(cmd)
      # Terminate this program when 
      if len(os.listdir(WORK_DIR)) == 1 and job_done:
        sys.exit(0)
