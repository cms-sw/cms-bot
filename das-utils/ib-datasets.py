#!/usr/bin/python
from os.path import dirname, basename, join, exists, abspath
from sys import exit, argv
from time import time, sleep
import json, sys
from commands import getstatusoutput
cmsbot_dir=None
if __file__: cmsbot_dir=dirname(dirname(abspath(__file__)))
else: cmsbot_dir=dirname(dirname(abspath(argv[0])))
sys.path.insert(0,cmsbot_dir)

from es_utils import get_payload

def format(s, **kwds): return s % kwds
query_url='http://cmses-master02.cern.ch:9200/ib-dataset-*/_search'
query_datsets = """
{
  "query": {
    "filtered": {
      "query": {
        "bool": {
          "should": [
            {
              "query_string": {
                "query": "release:%(release_cycle)s AND architecture:%(architecture)s",
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
  parser.add_option("-r", "--release",      dest="release", help="Release filter",   type=str, default="*")
  parser.add_option("-a", "--architecture", dest="arch",    help="SCRAM_ARCH filter. Production arch for a release cycle is used if found otherwise slc6_amd64_gcc530",   type=str, default=None)
  parser.add_option("-d", "--days",         dest="days",    help="Files access in last n days",   type=int, default=7)
  parser.add_option("-j", "--job",          dest="job",     help="Parallel jobs to run",   type=int, default=4)
  parser.add_option("-p", "--page",         dest="page_size", help="Page size, default 0 means no page and get all data in one go",  type=int, default=0)
  opts, args = parser.parse_args()
  
  if not opts.arch:
    if opts.release=="*": opts.arch="*"
    else:
      script_path = abspath(dirname(argv[0]))
      err, out = getstatusoutput("grep 'RELEASE_QUEUE=%s;' %s/config.map | grep -v 'DISABLED=1;' | grep 'PROD_ARCH=1;' | tr ';' '\n' | grep 'SCRAM_ARCH=' | sed 's|.*=||'" % (opts.release, script_path))
      if err: opts.arch="slc6_amd64_gcc530"
      else: opts.arch=out
  if opts.release!="*": opts.release=opts.release+"*"

  datasets = {}
  ent_from = 0
  json_out = []
  info_request = False
  queryInfo={}

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
  
  total_hits = 0
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
    json_out.append(content)
    if ent_from>=total_hits: break
  print json.dumps(json_out, indent=2, sort_keys=True, separators=(',',': '))

