#!/usr/bin/env python
from sys import exit, argv
from commands import getstatusoutput
from os.path import exists, getmtime
from os import environ
from time import time
import json
from hashlib import sha256
from optparse import OptionParser

parser = OptionParser(usage="%prog <options>")
parser.add_option("-t", "--time",       dest="time",      help="Refresh query results if previous resulst were older than time sec", default=86400)
parser.add_option("-o", "--override",   dest="override",  help="Override previous cache requests in cache empty results are returned from das", action="store_true", default=False)
opts, args = parser.parse_args()
das_queries_dir = "das_queries"

if not "CMSSW_VERSION" in environ:
  print "Error: Missing release env"
  exit (1)
release = environ["CMSSW_VERSION"]
if not "_X_" in release:
  print "Error: Env is not from CMSSW IB."
  exit(1)
cycle = "_".join(release.split("_X_",1)[0].split("_")[0:3])+"_X"
e, o = getstatusoutput("runTheMatrix.py -i all -n -e | grep 'input from:' | sed 's|  *.*input from:||;s| with run | |'")
if e:
  print o
  exit(1)

cache = {}
for line in o.split("\n"):
  block = None
  workflow, dataset, runs = line.split(" ",2)
  runs = runs.replace("[","").replace("]","").replace(" ","")
  if "#" in runs:
    block, runs = runs.split("#",1)
  query="dataset="+dataset
  if block:
    query = "block="+dataset+"#"+block
  cmds = []
  if runs:
    for run in runs.split(","):
      cache["file %s run=%s" % (query, run)] = []
  else:
    cache["file %s site=T2_CH_CERN" % query] = []

getstatusoutput("mkdir -p %s" % das_queries_dir)
das_cache = {}
query_sha = {}
for q in cache:
  sha = sha256(q).hexdigest()
  obj = "%s/%s/%s" % (das_queries_dir, sha[0:2], sha)
  query_sha [q] = obj
  print "Quering ",q
  if exists(obj):
    with open(obj) as json_data:
      jdata = json.load(json_data)
      if ((time()-jdata['mtime'])<=opts.time) and (len(jdata['files'])>0):
        print "  Found in cache"
        das_cache[q] = jdata['files']
        continue
      else:
        print "  Cache expired of no files found"
  print "  Searching DAS"
  err, out = getstatusoutput("das_client --format=json --limit=0 --query '%s' --retry=5 --threshold=600" % q)
  if err:
    print out
    continue
  jdata = json.loads(out)
  if (not "status" in jdata) or (jdata['status'] != 'ok') or (not "data" in jdata):
    print out
    continue
  results = {'mtime' : time(), 'files' : []}
  for item in jdata["data"]:
    if not item["file"]: continue
    results['files'].append(item["file"][0]["name"])
  if results['files'] or opts.override:
    das_cache[q] = results['files']
    if not exists("%s/%s" % (das_queries_dir,sha[0:2])):
      getstatusoutput("mkdir -f %s/%s" % (das_queries_dir,sha[0:2]))
    with open(obj, 'w') as outfile:
      json.dump(results, outfile)

for q in query_sha:
  obj = query_sha [q]
  if ((not q in das_cache) or (len(das_cache[q])==0)) and (exists(obj)):
    with open(obj) as json_data:
      jdata = json.load(json_data)
      das_cache[q] = jdata['files']
      print "Re-read: ",q

print "Generating das query cache for %s" % cycle
cyc_file = "%s/%s.json" % (das_queries_dir,cycle)
outfile = open("%s-tmp" % cyc_file, 'w')
if outfile:
  outfile.write(json.dumps(das_cache, sort_keys=True, indent=2,separators=(',',': ')))
  outfile.close()
  getstatusoutput("mv %s-tmp %s" %(cyc_file, cyc_file))




