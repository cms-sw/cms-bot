#!/usr/bin/env python
from sys import exit, argv
from commands import getstatusoutput
from os.path import exists, getmtime, dirname, basename
from os import environ
from time import time, sleep
import json, threading, re
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

def run_das_client(outfile, query, override, dasclient="das_client", threshold=900, retry=5, limit=0):
  sha=basename(outfile)
  fields = query.split(" ",1)[0].split(",")
  field_filter = ""
  field = fields[-1]
  if len(fields)==1:
    field_filter = " | grep %s.name | sort | unique" % field
  retry_str=""
  if dasclient=="das_client":retry_str="--retry=%s" % retry
  das_cmd = "%s --format=json --limit=%s --query '%s%s' %s --threshold=%s" % (dasclient, limit, query, field_filter, retry_str, threshold)
  print "  Running: ",sha,das_cmd
  print "  Fields:",sha,fields 
  err, out = getstatusoutput(das_cmd)
  if err:
    print "  ",sha,out
    return False
  try:
    jdata = json.loads(out)
  except Exception, e:
    print "  Failed to load josn output:%s:%s" %(sha,out)
    raise e
  if (not "status" in jdata) or (jdata['status'] != 'ok') or (not "data" in jdata):
    print "Failed: %s %s\n  %s" % (sha, query, out)
    return False
  results = {'mtime' : time(), 'results' : []}
  for item in jdata["data"]:
    if (not field in item) or (not item[field]) or (not 'name' in item[field][0]): continue
    results['results'].append(item[field][0]["name"])
  print "  Results:",sha,len(results['results'])
  if (len(results['results'])==0) and ('site=T2_CH_CERN' in query):
    query = query.replace("site=T2_CH_CERN","").strip()
    lmt = 0
    if "file" in fields: lmt = 100
    print "Removed T2_CH_CERN restrictions and limit set to %s: %s" % (lmt, query)
    return run_das_client(outfile, query, override, dasclient, threshold, retry, limit=lmt)
  if dasclient=="dasgoclient": override=True
  if results['results'] or override:
    write_json (outfile+".json", jdata)
    print "  Success %s '%s', found %s results." % (sha, query, len(results['results']))
    if results['results']:
      write_json (outfile, results)
    else:
      getstatusoutput("rm -f %s" % (outfile))
  return True

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <options>")
  parser.add_option("-t", "--threshold",  dest="threshold", help="Threshold time in sec to refresh query results. Default is 86400s", type=int, default=86400)
  parser.add_option("-o", "--override",   dest="override",  help="Override previous cache requests if cache empty results are returned from das", action="store_true", default=False)
  parser.add_option("-j", "--jobs",       dest="jobs",      help="Parallel das_client queries to run. Default is equal to cpu count but max value is 8", type=int, default=-1)
  parser.add_option("-s", "--store",      dest="store",     help="Name of object store directory to store the das queries results", default=None)
  parser.add_option("-c", "--client",     dest="client",    help="Das client to use either das_client or dasgoclient", default="das_client")
  parser.add_option("-q", "--query",      dest="query",     help="Only process this query", default=None)

  opts, args = parser.parse_args()
  if (not opts.store): parser.error("Missing store directory path to store das queries objects.")

  uqueries = {}
  query_sha = {}
  if opts.query:
    import hashlib
    query = re.sub("= ","=",re.sub(" =","=",re.sub("  +"," ",opts.query.strip())))
    uqueries[query] = []
    query_sha[query] = hashlib.sha256(query).hexdigest()
  else:
    err, qout = getstatusoutput("find %s -name '*.query' -type f" % opts.store)
    for qfile in qout.split("\n"):
      sha = basename(qfile).replace(".query","")
      qs = {}
      rewrite = False
      for query in [line.rstrip('\n').strip() for line in open(qfile)]:
        if not "=" in query: continue
        if "--query " in query:
          query = query.split("--query ")[1].split("'")[1]
          rewrite = True
        query = re.sub("= ","=",re.sub(" =","=",re.sub("  +"," ",query)))
        uqueries[query] = []
        query_sha[query]=sha
        qs[query]=1
      if rewrite:
        ofile = open(qfile, 'w')
        if ofile:
          for q in qs: ofile.write("%s\n" % q)
          ofile.close()

  tqueries = len(uqueries)
  print "Found %s unique queries" % (tqueries)
  jobs = opts.jobs
  if jobs <= 0:
    e, o = getstatusoutput("nproc")
    jobs = int(o)
  if jobs>8: jobs=8
  print "Parallel jobs:", jobs

  getstatusoutput("mkdir -p %s" % opts.store)
  threads = []
  nquery = 0
  inCache = 0 
  DasSearch = 0
  for query in uqueries:
    nquery += 1
    sha = query_sha[query]
    outfile = "%s/%s/%s" % (opts.store, sha[0:2], sha)
    print "[%s/%s] Quering %s '%s'" % (nquery, tqueries, sha, query)
    if exists(outfile):
      try:
        jdata = read_json (outfile)
        dtime = time()-jdata['mtime']
        if 'files' in jdata:
          jdata['results'] = jdata['files']
          del jdata['files']
          write_json (outfile, jdata)
        fcount = len(jdata['results'])
        if (dtime<=opts.threshold) and (fcount>0):
          jfile = "%s.json" % outfile
          okcache=exists(jfile)
          print " JSON results found",sha,okcache
          if okcache:
            xdata = read_json (jfile)
            if (not "status" in xdata) or (xdata['status'] != 'ok') or (not "data" in xdata):
              okcache=False
            else:
              for item in xdata["data"]:
                if not okcache: break
                for x in ["file", "lumi", "site"]:
                  if not x in item: continue
                  if len(item[x])>0: continue
                  okcache=False
                  break
          if okcache:
            uqueries[query] = jdata['results']
            print "  %s Found in cache with %s results (age: %s src)" % (sha, fcount , dtime)
            inCache += 1
            continue
          else: print "  Refreshing cache as previous Json was empty:", sha
        elif fcount>0: print "  Refreshing as cache expired (age: %s sec)" % dtime
        else: print "  Retrying as cache with empty results found."
      except IOError as e:
        print "  ERROR: [%s/%s] Reading json cached file %s" % (nquery, tqueries, outfile)
        e, o = getstatusoutput("cat %s" % outfile)
        print o
    else: print "  No cache file found %s" % sha
    
    DasSearch += 1
    while True:
      threads = [t for t in threads if t.is_alive()]
      tcount = len(threads)
      if(tcount < jobs):
        print "  Searching DAS (threads: %s)" % tcount
        try:
          t = threading.Thread(target=run_das_client, args=(outfile, query, opts.override, opts.client))
          t.start()
          threads.append(t)
          sleep(1)
        except Exception, e:
          print "ERROR threading das query cache: caught exception: " + str(e)
          error += 1
        break
      else:
        sleep(10)
  for t in threads: t.join()
  print "Total queries: %s" % tqueries
  print "Found in object store: %s" % inCache
  print "DAS Search: %s" % DasSearch
