#!/usr/bin/python
from os.path import dirname, basename, join, exists, abspath
from sys import exit, argv
from time import time, sleep
import json
from commands import getstatusoutput
from es_utils import get_payload, send_payload
from CMSWeb import CMSWeb, format

def download_file(store, lfn, protocol, dryRun):
  pfn_dir = dirname(store+lfn)
  pfn_file = basename(lfn)
  pfn = join (pfn_dir, pfn_file)
  if exists (pfn): return
  if dryRun:
    print "xrdcp -v %s%s %s" % (protocol, lfn, pfn)
    return
  if not exists(pfn_dir): getstatusoutput("mkdir -p %s" % (pfn_dir))
  err, out = getstatusoutput("rm -f %s.tmp; xrdcp -v %s%s %s.tmp" % (pfn, protocol, lfn, pfn))
  if err:
    getstatusoutput("rm -rf %s.tmp" % pfn)
    print "%s ==> [FAIL]\n%s" %(pfn, out)
  else:
    getstatusoutput("mv %s.tmp %s" % (pfn, pfn))
    print "%s ==> [DONE]" % pfn
  return

def download(lfns, store, jobs=4, dryRun=False):
  from threading import Thread
  total = len(lfns)
  index = 0
  threads = []
  while(index < total):
    threads = [t for t in threads if t.is_alive()]
    if(len(threads) < jobs):
      lfn = lfns[index][0]
      prot = lfns[index][1]
      index += 1
      print "Fetching [%s/%s] %s" % (index, total, lfn)
      try:
        t = Thread(target=download_file, args=(store, lfn, prot ,dryRun))
        t.start()
        threads.append(t)
      except Exception:
        print "Error: %s" % str(exc_info()[1])
        break
    else:
      sleep(0.1)
  for t in threads: t.join()
  return

query_url='http://cmses-master01.cern.ch:9200/ib-dataset-*/_search'
query_datsets = """
{
  "query": {
    "filtered": {
      "query": {
        "bool": {
          "should": [
            {
              "query_string": {
                "query": "release:%(release_cycle)s AND architecture:%(architecture)s%(update_opts)s",
                "lowercase_expanded_terms": false
              }
            }
          ]
        }
      },
      "filter": {
        "bool": {
          "must": [
            {
              "range": {
                "@timestamp": {
                  "from": %(start_time)s,
                  "to": %(end_time)s
                }
              }
            }
          ]
        }
      }
    }
  },
  "from": %(from)s,
  "size": %(page_size)s
}
"""

if __name__ == "__main__":
  from optparse import OptionParser  
  parser = OptionParser(usage="%prog ")
  parser.add_option("--json",               dest="json",    action="store_true", help="Do not download files but just dump the json results", default=False)
  parser.add_option("--datasets",           dest="datasets",action="store_true", help="Do not download files but dump datasets names", default=False)
  parser.add_option("--blocks",             dest="blocks",  action="store_true", help="Do not download files but dump blocks names", default=False)
  parser.add_option("--lfns",               dest="lfns",    action="store_true", help="Do not download files but dump uniq LFNS names", default=False)
  parser.add_option("--show-release",       dest="show_release",  action="store_true", help="show release name which uses the block", default=False)
  parser.add_option("--show-tests",         dest="show_tests",    action="store_true", help="show test name which uses the block", default=False)
  parser.add_option("--deprecated",         dest="deprecated",    action="store_true", help="show results/blocks which are deprecated", default=False)
  parser.add_option("--not-at-cern",        dest="not_at_cern",   action="store_true", help="show results which are not at cern", default=False)
  parser.add_option("--block-sites",        dest="block_sites",   action="store_true", help="Show sites where a dataset block replica exists", default=False)
  parser.add_option("--update",             dest="update",  action="store_true", help="Do not download file but update block/site info in ES", default=False)
  parser.add_option("--update-opts",        dest="update_opts",type=str,         help="Extra update guery options", default="ds_owner:UNKNOWN AND NOT ds_status:DEPRECATED")
  parser.add_option("-n", "--dry-run",      dest="dryRun",  action="store_true", help="Do not actually download the files", default=False)
  parser.add_option("-s", "--store",        dest="store",   help="Data store directory",   type=str, default="/build")
  parser.add_option("-r", "--release",      dest="release", help="Release filter",   type=str, default="*")
  parser.add_option("-a", "--architecture", dest="arch",    help="SCRAM_ARCH filter. Production arch for a release cycle is used if found otherwise slc6_amd64_gcc530",   type=str, default=None)
  parser.add_option("-d", "--days",         dest="days",    help="Files access in last n days",   type=int, default=7)
  parser.add_option("-j", "--job",          dest="job",     help="Parallel jobs to run",   type=int, default=4)
  parser.add_option("-p", "--page",         dest="page_size", help="Page size, default 0 means no page and get all data in one go",  type=int, default=0)
  opts, args = parser.parse_args()
  
  transfer = True
  if opts.datasets or opts.lfns or opts.blocks: opts.json=True
  if opts.update or opts.json: transfer = False
  if transfer and not opts.dryRun:
    err, out = getstatusoutput("which xrdcp")
    print out
    if err:
      print "Unable to find 'xrdcp' command."
      exit(1)

  if not opts.arch:
    if opts.release=="*": opts.arch="*"
    else:
      script_path = abspath(dirname(argv[0]))
      err, out = getstatusoutput("grep 'RELEASE_QUEUE=%s;' %s/config.map | grep -v 'DISABLED=1;' | grep 'PROD_ARCH=1;' | tr ';' '\n' | grep 'SCRAM_ARCH=' | sed 's|.*=||'" % (opts.release, script_path))
      if err: opts.arch="slc6_amd64_gcc530"
      else: opts.arch=out
  if opts.release!="*": opts.release=opts.release+"*"
  if not opts.json:
    print "Selected architecture:",opts.arch
    print "Selected release:",opts.release

  datasets = {}
  ent_from = 0
  json_out = []
  info_request = False
  queryInfo={"update_opts" : ""}

  queryInfo["end_time"] = int(time()*1000)
  queryInfo["start_time"] = queryInfo["end_time"]-int(86400*1000*opts.days)
  queryInfo["architecture"]=opts.arch
  queryInfo["release_cycle"]=opts.release
  queryInfo["from"]=0
  if opts.page_size<1:
    info_request = True
    queryInfo["page_size"]=2
  else:
    queryInfo["page_size"]=opts.page_size
  
  if opts.update and opts.update_opts:
    queryInfo["update_opts"]=" AND ( "+opts.update_opts+" )"
  total_hits = 0
  if not opts.json: print queryInfo
  while True:
    queryInfo["from"] = ent_from
    es_data = get_payload(query_url, format (query_datsets,**queryInfo))
    content = json.loads(es_data)
    content.pop("_shards", None)
    total_hits = content['hits']['total']
    if info_request:
      info_request = False
      queryInfo["page_size"]=total_hits
      continue
    hits = len(content['hits']['hits'])
    if hits==0: break
    ent_from = ent_from + hits
    if not transfer:
      json_out.append(content)
      if not opts.json: print "Found %s hits from %s to %s out of total %s" % (hits, ent_from-hits, ent_from, total_hits)
    else:
      print "Found %s hits from %s to %s out of total %s" % (hits, ent_from-hits, ent_from, total_hits)
      for hit in content['hits']['hits']: datasets[hit["_source"]["lfn"]]=hit["_source"]["protocol"]
    if ent_from>=total_hits: break

  if not transfer:
    if opts.json:
      if opts.datasets or opts.lfns or opts.blocks:
        ds = {"datasets" : {}, "lfns" : {}, "blocks" : {}}
        rels = {"datasets" : {}, "lfns" : {}, "blocks" : {}}
        for item in json_out:
          for h in item["hits"]["hits"]:
           if opts.not_at_cern and h["_source"]["at_cern"]=="yes": continue
           if opts.deprecated and h["_source"]["ds_status"]!="DEPRECATED": continue
           rel = "_".join(h["_source"]["release"].split("_")[0:3])+"_X"
           test = h["_source"]["name"]
           if opts.datasets and h["_source"]["dataset"] != "UNKNOWN":
             x ="datasets"
             k = h["_source"]["dataset"]
             ds[x][k]=1
             if not k in rels[x]: rels[x][k]={}
             if not rel in rels[x][k]: rels[x][k][rel]={}
             rels[x][k][rel][test]=1
           if opts.blocks and h["_source"]["ds_block"] != "UNKNOWN":
             x ="blocks"
             k = h["_source"]["ds_block"]
             ds[x][k]=1
             if not k in rels[x]: rels[x][k]={}
             if not rel in rels[x][k]: rels[x][k][rel]={}
             rels[x][k][rel][test]=1
           if opts.lfns:
             x ="lfns"
             k = h["_source"]["lfn"]
             ds[x][k]=1
             if not k in rels[x]: rels[x][k]={}
             if not rel in rels[x][k]: rels[x][k][rel]={}
             rels[x][k][rel][test]=1
        if opts.datasets:
          k = "datasets"
          ods = sorted(ds[k].keys())
          print "Datasets: %s" % len(ods)
          for b in ods:
            print "  Dataset: %s" % b
            if opt.show_release:
              x = []
              for r in sorted(rels[k][b].keys()):
                t = ""
                if opts.show_tests: t = " ("+",".join(sorted(rels[k][b][r].keys()))+")"
                x.append("%s%s" % (r,t))
              print "    Releases: %s " % ", ".join(x)
        if opts.blocks:
          k = "blocks"
          ods = sorted(ds[k].keys())
          cmsweb=None
          if opts.block_sites: cmsweb=CMSWeb()
          print "Blocks: %s" % (len(ods))
          for b in ods:
            print "  Block: %s" % b
            if opts.block_sites:
              cmsweb.search_block(b)
              print "    Replica: %s" % ",".join(cmsweb.cache["replicas"][b])
            if opts.show_release:
              x = []
              for r in sorted(rels[k][b].keys()):
                t = ""
                if opts.show_tests: t = " ("+",".join(sorted(rels[k][b][r].keys()))+")"
                x.append("%s%s" % (r,t))
              print "    Releases: %s " % ", ".join(x)
        if opts.lfns:
          k = "lfns"
          ods = sorted(ds[k].keys())
          print "LFNS: %s" % len(ods)
          for b in ods:
            print "  LFN: %s" % b
            if opt.show_release:
              x = []
              for r in sorted(rels[k][b].keys()):
                t = ""
                if opts.show_tests: t = " ("+",".join(sorted(rels[k][b][r].keys()))+")"
                x.append("%s%s" % (r,t))
              print "    Releases: %s " % ", ".join(x)
      else:
        print json.dumps(json_out, indent=2, sort_keys=True, separators=(',',': '))
    else:
      cmsweb=CMSWeb()
      lfns = {}
      ti = 0
      updated = 0
      for item in json_out:
        for h in item["hits"]["hits"]:
          ti+=1
          lfn_info = h["_source"]
          lfn_data = cmsweb.search(lfn_info["lfn"], lfn_info)
          update = False
          for item in lfn_data:
            if (not item in lfn_info) or (lfn_data[item] != lfn_info[item]):
              lfn_info[item]=lfn_data[item]
              update = True
          print "Processing .... %s/%s (LFNS: %s, NEW LFN: %s, DS: %s, BLK:%s, ERR: %s):  %s" % (ti, total_hits ,len(cmsweb.cache['lfns']),  len(cmsweb.cache['new_lfns']), len(cmsweb.cache['datasets']), len(cmsweb.cache['blocks']), cmsweb.errors, update)
          if update:
            send_payload(h['_index'], h['_type'], h['_id'], json.dumps(lfn_info))
            updated += 1
      print "Updated Records:", updated
    exit(0)
  lfns = []
  for lfn in datasets: lfns.append([lfn, datasets[lfn]])
  download(lfns, opts.store, opts.job,opts.dryRun)
  print "Total Files:",len(datasets)
