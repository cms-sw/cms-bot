#!/usr/bin/env python
from sys import exit, argv
from commands import getstatusoutput
from os.path import exists, getmtime, dirname
from os import environ
from time import time, sleep
import json, threading
from hashlib import sha256
from optparse import OptionParser
from RelValArgs import GetMatrixOptions

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
  parser.add_option("-q", "--query",      dest="query",     help="Name of the file to contains the das queries to run.", default=None)
  parser.add_option("-c", "--cache",      dest="cache",     help="Name of the cache file name e.g. CMSSW_8_1_X.json", default=None)
  parser.add_option("-s", "--store",      dest="store",     help="Name of object store directory to store the das queries results", default=None)

  opts, args = parser.parse_args()
  if (not opts.query) or (not exists(opts.query)): parser.error("Missing das query file.")
  if (not opts.cache): parser.error("Missing cache file name to store the results.")
  if (not opts.store): parser.error("Missing store directory path to store das queries objects.")

  cache = {}
  for query in [line.rstrip('\n').strip() for line in open(opts.query)]:
    cache[query] = []

  print "Found %s uniq queries" % len(cache)
  jobs = opts.jobs
  if jobs <= 0:
    e, o = getstatusoutput("nproc")
    jobs = int(o)
  if jobs>8: jobs=8
  print "Parallel jobs:", jobs

  getstatusoutput("mkdir -p %s" % opts.store)
  query_sha = {}
  das_cache = {}
  threads = []
  for query in cache:
    sha = sha256(query).hexdigest()
    outfile = "%s/%s/%s" % (opts.store, sha[0:2], sha)
    query_sha [query] = outfile
    print "Quering ",query
    if exists(outfile):
      jdata = read_json (outfile)
      dtime = time()-jdata['mtime']
      fcount = len(jdata['files'])
      if (dtime<=opts.time) and (fcount>0):
        das_cache[query] = jdata['files']
        print "  Found in cache with %s files (age: %s src)" % (fcount , dtime)
        continue
      elif fcount>0: print "  Refreshing as cache expired (age: %s sec)" % dtime
      else: print "  Retrying as cache with empty file list found."

    while True:
      threads = [t for t in threads if t.is_alive()]
      tcount = len(threads)
      if(tcount < jobs):
        print "  Searching DAS (threads: %s)" % tcount
        try:
          t = threading.Thread(target=run_das_client, args=(outfile, query, opts.override))
          t.start()
          threads.append(t)
          sleep(1)
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

  print "Generating das query cache for %s" % opts.cache
  write_json(opts.cache, das_cache)




