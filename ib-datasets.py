#!/usr/bin/python
from os.path import dirname, basename, join, exists, abspath
from os import getuid
from sys import exit, argv
from time import time, sleep
from urllib import urlencode
from httplib import HTTPSConnection
import json
from commands import getstatusoutput
from es_utils import get_payload, send_payload
def format(s, **kwds): return s % kwds
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

class CMSWeb (object):
  def __init__ (self):
    self.URL_CMSWEB_BASE='cmsweb.cern.ch'
    self.URL_PHEDEX_BLOCKREPLICAS='/phedex/datasvc/json/prod/blockreplicas'
    self.URL_DBS_DATASETS='/dbs/prod/global/DBSReader/datasets'
    self.URL_DBS_FILES='/dbs/prod/global/DBSReader/files'
    self.URL_DBS_BLOCKS='/dbs/prod/global/DBSReader/blocks'
    self.conn = HTTPSConnection(self.URL_CMSWEB_BASE, cert_file='/tmp/x509up_u{0}'.format(getuid()),  timeout=30)
    self.cache = {'lfns':{}, 'datasets': {}, 'blocks': {}, 'new_lfns' : {}}
    self.errors = 0

  def __del__(self): self.conn.close ()

  def get_cmsweb_data(self, url):
    msg =""
    try:
      self.conn.request('GET', url)
      msg = self.conn.getresponse()
      if msg.status!=200:
        self.errors = self.errors + 1
        print 'Result: {0} {1}: {2}'.format(msg.status, msg.reason, url)
        return False, {}
      return True, json.loads(msg.read())
    except Exception, e:
      print "Error:", e, url
      self.errors = self.errors + 1
      return False, {}

  def search(self, lfn, lfn_info):
    if lfn in self.cache['lfns']: return self.cache['lfns'][lfn]
    self.cache['lfns'][lfn] = self.search_(lfn, lfn_info)
    #print "NEW:",self.cache['lfns'][lfn]
    return self.cache['lfns'][lfn]

  def search_(self, lfn, lfn_info):
    #print "CUR:",lfn_info
    lfn_data = {}
    for x in ["ds_status", "ds_block", "ds_owner", "at_cern", "dataset"]:
      if (not x in lfn_info) or (lfn_info[x]==""): lfn_data[x]="UNKNOWN"
    if (not "ds_files" in lfn_info) or (lfn_info["ds_files"]==""): lfn_data["ds_files"]="0"
    # Find the block
    if lfn_info['ds_block']=='UNKNOWN':
      self.cache['new_lfns'][lfn]=1
      status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_DBS_BLOCKS, urlencode({'detail': 1,'logical_file_name': lfn})))
      if not status: return lfn_data
      lfn_data['ds_block'] = jmsg[0]['block_name']
      lfn_data['dataset']  = jmsg[0]['dataset']
    else:
      lfn_data['ds_block'] = lfn_info['ds_block']
      lfn_data['dataset']  = lfn_info['dataset']

    block = lfn_data['ds_block']
    dataset = lfn_data['dataset']
    # Check if dataset is still VALID
    if not dataset in self.cache['datasets']:
      status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_DBS_DATASETS, urlencode({'detail': 1, 'dataset_access_type': '*', 'dataset': dataset})))
      if not status: return lfn_data
      self.cache['datasets'][dataset] = jmsg[0]['dataset_access_type'].strip().replace(" ","_")
    lfn_data['ds_status'] = self.cache['datasets'][dataset]

    # Check if dataset/block exists at T2_CH_CERN and belongs to IB RelVals group
    if not block in self.cache['blocks']:
      status, jmsg = self.get_cmsweb_data('{0}?{1}'.format(self.URL_PHEDEX_BLOCKREPLICAS, urlencode({'block': block})))
      if not status: return lfn_data
      if len(jmsg['phedex']['block']) == 0: return lfn_data
      block_data = {'at_cern' : 'no'}
      for replica in jmsg['phedex']['block'][0]['replica']:
        if replica['node'] != 'T2_CH_CERN': continue
        block_data['at_cern'] = 'yes'
        block_data['ds_files'] = str(replica['files'])
        block_data['ds_owner'] = replica['group'].strip().replace(" ","_")
        break
      self.cache['blocks'][block]={}
      for x in block_data: self.cache['blocks'][block][x]=block_data[x]
    for x in self.cache['blocks'][block]: lfn_data[x] = self.cache['blocks'][block][x]
    return lfn_data

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
  parser = OptionParser(usage="%prog <pull-request-id>")
  parser.add_option("--json",               dest="json",    action="store_true", help="Do not download files but just dump the json results", default=False)
  parser.add_option("--datasets",           dest="datasets",action="store_true", help="Do not download files but dump datasets names", default=False)
  parser.add_option("--update",             dest="update",  action="store_true", help="Do not download file but update block/site info in ES", default=False)
  parser.add_option("-n", "--dry-run",      dest="dryRun",  action="store_true", help="Do not actually download the files", default=False)
  parser.add_option("-s", "--store",        dest="store",   help="Data store directory",   type=str, default="/build")
  parser.add_option("-r", "--release",      dest="release", help="Release filter",   type=str, default="CMSSW_8_1_X")
  parser.add_option("-a", "--architecture", dest="arch",    help="SCRAM_ARCH filter. Production arch for a release cycle is used if found otherwise slc6_amd64_gcc530",   type=str, default=None)
  parser.add_option("-d", "--days",         dest="days",    help="Files access in last n days",   type=int, default=7)
  parser.add_option("-j", "--job",          dest="job",     help="Parallel jobs to run",   type=int, default=4)
  parser.add_option("-p", "--page",         dest="page_size", help="Page size, default 0 means no page and get all data in one go",  type=int, default=0)
  opts, args = parser.parse_args()
  
  transfer = True
  if opts.datasets: opts.json=True
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
  
  if opts.update:
    queryInfo["update_opts"]=" AND ds_owner:UNKNOWN AND NOT ds_status:DEPRECATED"
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
      if opts.datasets:
        ds = {}
        for item in json_out:
          for h in item["hits"]["hits"]:
           if h["_source"]["dataset"] == "UNKNOWN": continue
           ds[h["_source"]["dataset"]]=1
        ods = sorted(ds.keys())
        print "\n".join(ods)
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
