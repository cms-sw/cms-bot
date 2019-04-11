#!/usr/bin/env python
from __future__ import print_function
from sys import exit
from os.path import exists,  dirname, abspath ,basename, join
from time import time, sleep
import json, threading, re
from optparse import OptionParser

import sys
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

field_map = {'file':'name', 'lumi':'number', 'site':'name', 'run':'run_number', 'dataset':'name'}

def write_json(outfile, cache):
  outdir = dirname(outfile)
  if not exists(outdir): run_cmd("mkdir -p %s" % outdir)
  ofile = open(outfile, 'w')
  if ofile:
    ofile.write(json.dumps(cache, sort_keys=True, indent=2,separators=(',',': ')))
    ofile.close()

def read_json(infile):
  with open(infile) as json_data:
    return json.load(json_data)

def run_das_client(outfile, query, override, dasclient="das_client", threshold=900, retry=5, limit=0):
  sha=basename(outfile)
  field = query.split(" ",1)[0]
  if "=" in field: field=field.split("=",1)[0]
  fields = field.split(",")
  field_filter = ""
  field = fields[-1]
  if field in ["file", "site", "dataset"]:
    field_filter = " | grep %s.name | sort %s.name | unique" % (field, field)
  retry_str=""
  if dasclient=="das_client":retry_str="--retry=%s" % retry
  das_cmd = "%s --format=json --limit=%s --query '%s%s' %s --threshold=%s" % (dasclient, limit, query, field_filter, retry_str, threshold)
  print("  Running: ",sha,das_cmd)
  print("  Fields:",sha,fields) 
  err, out = run_cmd(das_cmd)
  efile = "%s.error" % outfile
  with open(efile, "w") as ofile:
    ofile.write(out)
  if err:
    print("  DAS ERROR:",sha)
    return False
  try:
    jdata = json.loads(out)
  except Exception as e:
    print("  Failed to load das output:",sha,e)
    return False
  if (not "status" in jdata) or (jdata['status'] != 'ok') or (not "data" in jdata) or (("ecode" in jdata) and (jdata['ecode']!="")):
    print("Failed: %s %s\n  %s" % (sha, query, out))
    return False
  all_ok = True
  for fx in fields:
    fn = field_map[fx]
    for item in jdata['data']:
      if (not fx in item) or (not item[fx]) or (not fn in item[fx][0]) or (item[fx][0][fn] is None): all_ok = False
  if not all_ok:
    print("  DAS WRONG Results:",fields,sha,out)
    return False
  run_cmd("rm -f %s" % efile)
  results = []
  for item in jdata["data"]:
    res = str(item[field][0][field_map[field]])
    xf = 'lumi'
    if (len(fields)>1) and (fields[0]==xf):
      res = res + " [" +",".join([str(i) for i in item[xf][0][field_map[xf]]])+ "]"
    if not res in results: results.append(res)
  print("  Results:",sha,len(results))
  if (len(results)==0) and ('site=T2_CH_CERN' in query):
    query = query.replace("site=T2_CH_CERN","").strip()
    lmt = 0
    if "file" in fields: lmt = 100
    print("Removed T2_CH_CERN restrictions and limit set to %s: %s" % (lmt, query))
    return run_das_client(outfile, query, override, dasclient, threshold, retry, limit=lmt)
  if results or override:
    xfile = outfile+".json"
    write_json (xfile+".tmp", jdata)
    if exists (xfile):
      e, o = run_cmd("diff -u %s %s.tmp | grep '^+ ' | sed 's| ||g;s|\"||g;s|^+[a-zA-Z0-9][a-zA-Z0-9_]*:||;s|,$||' | grep -v '[0-9][0-9]*\(\.[0-9]*\|\)$'" % (xfile,xfile))
      if o:
        run_cmd("mv %s.tmp %s" % (xfile,xfile))
      else:
        run_cmd("rm %s.tmp" % xfile)
    else:
      run_cmd("mv %s.tmp %s" % (xfile,xfile))
    print("  Success %s '%s', found %s results." % (sha, query, len(results)))
    if results:
      with open(outfile, "w") as ofile:
        for res in sorted(results):
          ofile.write(res+'\n')
      run_cmd("echo '%s' > %s.timestamp" % (int(time()), outfile))
    else:
      run_cmd("rm -f %s" % (outfile))
  return True

def cleanup_timestamps(store):
  run_cmd("find %s -name '*.timestamp' | xargs rm -f" % store)
  run_cmd("find %s -name '*.tmp'       | xargs rm -f" % store)
  run_cmd("find %s -name '*.error'     | xargs rm -f" % store)

def read_timestramps(timestramps_file):
  timestramps = {}
  if exists (timestramps_file): timestramps = read_json (timestramps_file)
  return timestramps

def update_timestamp(timestramps, timestramps_file, store):
  e, o = run_cmd("find %s -name '*.timestamp'" % store)
  for ts_file in o.split("\n"):
    if not ts_file.endswith('.timestamp'): continue
    sha = basename(ts_file).replace(".timestamp","")
    with open(ts_file) as f:
      timestramps[sha] = int(float(f.readlines()[0].strip()))
  write_json(timestramps_file, timestramps)
  cleanup_timestamps(store)

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <options>")
  parser.add_option("-t", "--threshold",  dest="threshold", help="Threshold time in sec to refresh query results. Default is 86400s", type=int, default=86400)
  parser.add_option("-o", "--override",   dest="override",  help="Override previous cache requests if cache empty results are returned from das", action="store_true", default=False)
  parser.add_option("-j", "--jobs",       dest="jobs",      help="Parallel das_client queries to run. Default is equal to cpu count but max value is 32", type=int, default=-1)
  parser.add_option("-s", "--store",      dest="store",     help="Name of object store directory to store the das queries results", default=None)
  parser.add_option("-c", "--client",     dest="client",    help="Das client to use either das_client or dasgoclient", default="das_client")
  parser.add_option("-q", "--query",      dest="query",     help="Only process this query", default=None)

  opts, args = parser.parse_args()
  if (not opts.store): parser.error("Missing store directory path to store das queries objects.")

  query_sha = {}
  if opts.query:
    import hashlib
    query = re.sub("= ","=",re.sub(" =","=",re.sub("  +"," ",opts.query.strip())))
    query_sha[query] = hashlib.sha256(query).hexdigest()
  else:
    err, qout = run_cmd("find %s -name '*.query' -type f" % opts.store)
    for qfile in qout.split("\n"):
      sha = basename(qfile).replace(".query","")
      if not sha: continue
      qs = {}
      rewrite = False
      for query in [line.rstrip('\n').strip() for line in open(qfile)]:
        if not "=" in query: continue
        if "--query " in query:
          query = query.split("--query ")[1].split("'")[1]
          rewrite = True
        query = re.sub("= ","=",re.sub(" =","=",re.sub("  +"," ",query)))
        query_sha[query]=sha
        qs[query]=1
      if rewrite:
        ofile = open(qfile, 'w')
        if ofile:
          for q in qs: ofile.write("%s\n" % q)
          ofile.close()

  xqueries = {}
  for query in query_sha:
    if 'site=T2_CH_CERN' in query:
      query = re.sub("  +"," ",query.replace('site=T2_CH_CERN','').strip())
      if not query in query_sha:
        from hashlib import sha256
        sha = sha256(query).hexdigest()
        xqueries[query] = sha
        qdir = join(opts.store, sha[:2])
        run_cmd("mkdir -p %s" % qdir)
        with open(join(qdir, sha+'.query'), "w") as ofile:
          ofile.write("%s\n" % query)

  for query in xqueries:
    query_sha[query] = xqueries[query]
    print("Added new query: %s => %s" % (query_sha[query], query))
  tqueries = len(query_sha)
  print("Found %s unique queries" % (tqueries))
  jobs = opts.jobs
  if jobs <= 0:
    e, o = run_cmd("nproc")
    jobs = int(o)
  if jobs>32: jobs=32
  print("Parallel jobs:", jobs)

  run_cmd("mkdir -p %s" % opts.store)
  threads = []
  nquery = 0
  inCache = 0 
  DasSearch = 0
  error = 0
  cleanup_timestamps (opts.store)
  timestramps_file = join (opts.store, "timestamps.json")
  timestramps = read_timestramps (timestramps_file)
  for query in query_sha:
    nquery += 1
    sha = query_sha[query]
    outfile = "%s/%s/%s" % (opts.store, sha[0:2], sha)
    print("[%s/%s] Quering %s '%s'" % (nquery, tqueries, sha, query))
    if exists(outfile):
      xtime  = 0
      fcount = 0
      if sha in timestramps:
        xtime = timestramps[sha]
        with open(outfile) as ofile:
          fcount = len(ofile.readlines())
      dtime = int(time())-xtime
      if (dtime<=opts.threshold) and (fcount>0):
        jfile = "%s.json" % outfile
        okcache=exists(jfile)
        print(" JSON results found",sha,okcache)
        if okcache:
          try:
            xdata = read_json (jfile)
            if (not "status" in xdata) or (xdata['status'] != 'ok') or (not "data" in xdata):
              okcache=False
            else:
              for item in xdata["data"]:
                if not okcache: break
                for x in field_map:
                  if not x in item: continue
                  if len(item[x])>0: continue
                  okcache=False
                  break
          except IOError as e:
            print("  ERROR: [%s/%s] Reading json cached file %s" % (nquery, tqueries, outfile))
            e, o = run_cmd("cat %s" % outfile)
            print(o)
            okcache=False
        if okcache:
          print("  %s Found in cache with %s results (age: %s src)" % (sha, fcount , dtime))
          inCache += 1
          continue
        else: print("  Refreshing cache as previous Json was empty:", sha)
      elif fcount>0: print("  Refreshing as cache expired (age: %s sec)" % dtime)
      else: print("  Retrying as cache with empty results found.")
    else: print("  No cache file found %s" % sha)

    DasSearch += 1
    while True:
      tcount = len(threads)
      if(tcount < jobs):
        print("  Searching DAS (threads: %s)" % tcount)
        try:
          t = threading.Thread(target=run_das_client, args=(outfile, query, opts.override, opts.client))
          t.start()
          threads.append(t)
          sleep(1)
        except Exception as e:
          print("ERROR threading das query cache: caught exception: " + str(e))
          error += 1
        break
      else:
        threads = [t for t in threads if t.is_alive()]
        sleep(0.2)
  for t in threads: t.join()
  failed_queries = 0
  e , o = run_cmd("find %s -name '*.error'" % opts.store)
  for f in o.split("\n"):
    if not f.endswith(".error"): continue
    qf = f.replace(".error",".query")
    print("########################################")
    e , o = run_cmd("cat %s ; cat %s" % (qf, f))
    print(o)
    failed_queries += 1
  print("Total queries: %s" % tqueries)
  print("Found in object store: %s" % inCache)
  print("DAS Search: %s" % DasSearch)
  print("Total Queries Failed:",failed_queries)
  print("Process state:",error)
  if not error:update_timestamp(timestramps, timestramps_file, opts.store)
  else:  cleanup_timestamps (opts.store)
  exit(error)
