#!/usr/bin/env python
from sys import exit, argv
from commands import getstatusoutput
from os.path import exists, getmtime, dirname
from os import environ
from time import time, sleep
import json, threading
from hashlib import sha256
from optparse import OptionParser

def write_json(outfile, cache):
  outdir = dirname(outfile)
  if not exists(outdir): getstatusoutput("mkdir -p %s" % outdir)
  ofile = open(outfile, 'w')
  if ofile:
    ofile.write(json.dumps(cache, sort_keys=True, indent=2,separators=(',',': ')))
    ofile.close()

def read_json(infile):
  with open(infile) as json_data:
    return json.load(json_data)

def run_das_client(outfile, query, override, threshold=900, retry=5, limit=0):
  err, out = getstatusoutput("das_client --format=json --limit=%s --query '%s' --retry=%s --threshold=%s" % (limit, query,retry, threshold))
  if err:
    print out
    return False
  jdata = json.loads(out)
  if (not "status" in jdata) or (jdata['status'] != 'ok') or (not "data" in jdata):
    print out
    return False
  results = {'mtime' : time(), 'files' : []}
  for item in jdata["data"]:
    if (not item["file"]) or (not 'name' in item["file"][0]): continue
    results['files'].append(item["file"][0]["name"])
  if results['files'] or override:
    print "  Success %s, found %s files." % (query, len(results['files']))
    write_json (outfile, results)
  return True

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <options>")
  parser.add_option("-t", "--time",       dest="time",      help="Refresh query results if previous resulst were older than time sec", default=86400)
  parser.add_option("-o", "--override",   dest="override",  help="Override previous cache requests in cache empty results are returned from das", action="store_true", default=False)
  parser.add_option("-j", "--jobs",       dest="jobs",      help="Parallel das_client queries to run. Default is equal to cpu count but max value is 8", default=-1)
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
  print "Release cycle:",cycle
  e, o = getstatusoutput("runTheMatrix.py -i all -n -e | grep 'input from:' | sed 's|  *.*input from:||;s| with run | |'")
  if e:
    print o
    exit(1)

  cache = {}
  for line in o.split("\n"):
    block = None
    try:
      workflow, dataset, runs = line.split(" ",2)
    except:
      print "Error parsing: ",line
      exit(1)
      
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

  jobs = opts.jobs
  if jobs <= 0:
    e, o = getstatusoutput("nproc")
    jobs = int(o)
  if jobs>8: jobs=8
  print "Parallel jobs:", jobs

  getstatusoutput("mkdir -p %s" % das_queries_dir)
  query_sha = {}
  das_cache = {}
  threads = []
  for query in cache:
    sha = sha256(query).hexdigest()
    outfile = "%s/%s/%s" % (das_queries_dir, sha[0:2], sha)
    query_sha [query] = outfile
    print "Quering ",query
    if exists(outfile):
      jdata = read_json (outfile)
      if ((time()-jdata['mtime'])<=opts.time) and (len(jdata['files'])>0):
        das_cache[query] = jdata['files']
        print "  Found in cache"
        continue
      else: print "  Cache expired of no files found"

    while True:
      threads = [t for t in threads if t.is_alive()]
      tcount = len(threads)
      if(tcount < jobs):
        print "  Searching DAS (threads: %s)" % tcount
        try:
          t = threading.Thread(target=run_das_client, args=(outfile, query, opts.override))
          t.start()
          threads.append(t)
          sleep(5)
        except Exception, e:
          print "ERROR threading das query cache: caught exception: " + str(e)
        break
      else:
        sleep(10)
  for t in threads: t.join()

  for query in query_sha:
    obj = query_sha [query]
    if ((not query in das_cache) or (len(das_cache[query])==0)) and exists(obj):
      jdata = read_json (obj)
      das_cache[query] = jdata['files']

  print "Generating das query cache for %s" % cycle
  write_json("%s/%s.json" % (das_queries_dir,cycle), das_cache)




