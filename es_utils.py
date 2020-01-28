#!/usr/bin/env python
from __future__ import print_function
import json, re, ssl
from os.path import exists
from os import getenv
from hashlib import sha1
from cmsutils import cmsswIB2Week, percentile
from _py2with3compatibility import HTTPPasswordMgrWithDefaultRealm, HTTPBasicAuthHandler, install_opener, Request, \
  urlopen, build_opener
from os import stat as tstat
from datetime import datetime

CMSSDT_ES_QUERY="https://cmssdt.cern.ch/SDT/cgi-bin/es_query"
ES_SERVER = 'https://es-cmssdt.cern.ch:9203'
def format(s, **kwds): return s % kwds

def get_es_query(query="", start_time=0, end_time=0, page_start=0, page_size=10000, timestamp_field='@timestamp', lowercase_expanded_terms='false', fields=None):
  es5_query_tmpl="""{
  "_source": [%(fields_list)s],
  "query":
    {
    "bool":
      {
        "must": { "query_string": { "query": "%(query)s"}},
        "must": { "range":  { "%(timestamp_field)s": { "gte": %(start_time)s, "lte":%(end_time)s}}}
      }
    },
    "sort": [{"%(timestamp_field)s": "desc" }],
    "from" : %(page_start)s,
    "size" : %(page_size)s
  }"""
  if not fields: fields = ["*"]
  fields_list = ",".join([ '"%s"' % f for f in fields])
  return format(es5_query_tmpl, **locals ())

def resend_payload(hit, passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  return send_payload(hit["_index"], hit["_type"], hit["_id"],json.dumps(hit["_source"]),passwd_file=passwd_file)

def es_get_passwd(passwd_file=None):
  for psfile in [passwd_file, getenv("CMS_ES_SECRET_FILE",None), "/data/secrets/cmssdt-es-secret", "/build/secrets/cmssdt-es-secret", "/var/lib/jenkins/secrets/cmssdt-es-secret", "/data/secrets/github_hook_secret_cmsbot"]:
    if not psfile: continue
    if exists(psfile):
      passwd_file=psfile
      break
  try:
    return open(passwd_file,'r').read().strip()
  except Exception as e:
    print("Couldn't read the secrets file" , str(e))
    return ""

def send_request(uri, payload=None, passwd_file=None, method=None):
  passwd=es_get_passwd(passwd_file)
  if not passwd: return False
  url = "%s/%s" % (ES_SERVER,uri)
  passman = HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'cmssdt', passwd)
  auth_handler = HTTPBasicAuthHandler(passman)
  opener = build_opener(auth_handler)
  try:
    install_opener(opener)
    request = Request(url, payload)
    if method: request.get_method = lambda: method
    content = urlopen(request)
  except Exception as e:
    print("ERROR:",url,str(e))
    return False
  return True

def send_payload(index, document, id, payload, passwd_file=None):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  uri = "%s/%s/" % (index,document)
  if id: uri = uri+id
  if not send_request(uri, payload=payload, passwd_file=passwd_file): return False
  print("OK ",index)
  return True

def send_template(name, payload, passwd_file=None):
  if not name.startswith('cmssdt-'): name = 'cmssdt-' + name
  uri = "_template/%s" % name
  if not send_request(uri, payload=payload, passwd_file=passwd_file, method='PUT'): return False
  print("OK ",name)
  return True

def delete_hit(hit,passwd_file=None):
  uri = "%s/%s/%s" % (hit["_index"], hit["_type"], hit["_id"])
  if not send_request(uri, passwd_file=passwd_file, method='DELETE'): return False
  print("DELETE:",hit["_id"])
  return True

def get_payload(index, query, scroll=0):
  data = {'index':index, 'query':query, 'scroll':scroll}
  sslcon = None
  try:
    sslcon = ssl._create_unverified_context()
  except Exception as e:
    sslcon =  None
  if sslcon: return urlopen(CMSSDT_ES_QUERY,json.dumps(data).encode("ascii","ignore"), context=sslcon).read()
  else: return urlopen(CMSSDT_ES_QUERY,json.dumps(data).encode("ascii","ignore")).read()

def get_payload_wscroll(index, query, max_count=-1):
  es_data = json.loads(get_payload(index, query,scroll=1))
  if 'proxy-error' in es_data: return es_data
  es_data.pop("_shards", None)
  scroll_size = es_data['hits']['total']
  scroll_id = es_data.pop('_scroll_id')
  tcount = 0
  while ((scroll_size > 0) and ((max_count<0) or (tcount<max_count))):
    query = '{"scroll_id": "%s","scroll":"1m"}' % scroll_id
    es_xdata = json.loads(get_payload(index,query,scroll=2))
    if 'proxy-error' in es_xdata: return es_xdata
    scroll_id = es_xdata.pop('_scroll_id')
    scroll_size = len(es_xdata['hits']['hits'])
    tcount += scroll_size
    if (scroll_size > 0): es_data['hits']['hits']+=es_xdata['hits']['hits']
  return es_data

def get_template(index=''):
  data = {'index':index, 'api': '/_template', 'prefix': True}
  return urlopen(CMSSDT_ES_QUERY,json.dumps(data)).read()

def find_indexes(index):
  idxs = {}
  for line in get_indexes(index).split("\n"):
    line=re.sub("\s\s+"," ",line.strip())
    if not line: continue
    data =line.split(" ")
    idx = ""
    st = data[0]
    if st == "close":
      idx = data[1]
    else:
      st = data[1]
      idx = data[2]
    if not st in idxs: idxs[st]=[]
    idxs[st].append(idx)
  return idxs

def get_indexes(index='cmssdt-*'):
  data = {'index':index, 'api': '/_cat', 'prefix': True}
  return urlopen(CMSSDT_ES_QUERY,json.dumps(data)).read()

def close_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/_close',method='POST')

def open_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/_open',method='POST')

def delete_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/',method='DELETE')

def es_query(index,query,start_time,end_time,page_start=0,page_size=10000,timestamp_field="@timestamp", scroll=False, max_count=-1, fields=None):
  query_str = get_es_query(query=query, start_time=start_time,end_time=end_time,page_start=page_start,page_size=page_size,timestamp_field=timestamp_field, fields=fields)
  if scroll: return get_payload_wscroll(index, query_str, max_count)
  return json.loads(get_payload(index, query_str))

def es_workflow_stats(es_hits,rss='rss_75', cpu='cpu_75'):
  wf_stats = {}
  for h in es_hits['hits']['hits']:
    hit = h["_source"]
    wf = hit["workflow"]
    step = hit["step"]
    if not wf in wf_stats: wf_stats[wf]={}
    if not step in wf_stats[wf]:wf_stats[wf][step]=[]
    wf_stats[wf][step].append([hit['time'], hit[rss], hit[cpu], hit["rss_max"], hit["cpu_max"]])

  for wf in wf_stats:
    for step in wf_stats[wf]:
      hits = wf_stats[wf][step]
      thits = len(hits)
      time_v = int(sum([h[0] for h in hits])/thits)
      rss_v = int(sum([h[1] for h in hits])/thits)
      cpu_v = int(sum([h[2] for h in hits])/thits)
      rss_m = int(sum([h[3] for h in hits])/thits)
      cpu_m = int(sum([h[4] for h in hits])/thits)
      if rss_v<1024: rss_v = rss_m
      if cpu_v<10: cpu_v = cpu_m
      wf_stats[wf][step] = { "time"  : time_v,
                             "rss"   : rss_v,
                             "cpu"   : cpu_v,
                             "rss_max" : rss_m,
                             "cpu_max" : cpu_m,
                             "rss_avg" : int((rss_v+rss_m)/2),
                             "cpu_avg" : int((cpu_v+cpu_m)/2)
                           }
  return wf_stats

def get_summary_stats_from_dictionary(stats_dict, cpu_normalize):
  sdata = None
  try:
    xdata = {}
    for stat in stats_dict:
      for item in stat:
        try:
          xdata[item].append(stat[item])
        except:
          xdata[item] = []
          xdata[item].append(stat[item])
    sdata = {}
    for x in xdata:
      data = sorted(xdata[x])
      if x in ["time", "num_threads", "processes", "num_fds"]:
        sdata[x] = data[-1]
        continue
      if not x in ["rss", "vms", "pss", "uss", "shared", "data", "cpu"]: continue
      dlen = len(data)
      if (x == "cpu") and (cpu_normalize > 1) and (data[-1] > 100):
        data = [d / cpu_normalize for d in data]
      for t in ["min", "max", "avg", "median", "25", "75", "90"]: sdata[x + "_" + t] = 0
      if dlen > 0:
        sdata[x + "_min"] = data[0]
        sdata[x + "_max"] = data[-1]
        if dlen > 1:
          dlen2 = int(dlen / 2)
          if (dlen % 2) == 0:
            sdata[x + "_median"] = int((data[dlen2 - 1] + data[dlen2]) / 2)
          else:
            sdata[x + "_median"] = data[dlen2]
          sdata[x + "_avg"] = int(sum(data) / dlen)
          for t in [25, 75, 90]:
            sdata[x + "_" + str(t)] = int(percentile(t, data, dlen))
        else:
          for t in ["25", "75", "90", "avg", "median"]:
            sdata[x + "_" + t] = data[0]
  except Exception as e:
    print(e.message)
  return sdata

def es_send_resource_stats(release, arch, name, version, sfile,
                           hostname, exit_code, params=None,
                           cpu_normalize=1, index="relvals_stats_summary", doc="runtime-stats-summary"):
  week, rel_sec  = cmsswIB2Week(release)
  rel_msec = rel_sec*1000
  if "_X_" in release:
    release_queue = release.split("_X_",1)[0]+"_X"
  else:
    release_queue = "_".join(release.split("_")[:3])+"_X"
  sdata = {"release": release, "release_queue": release_queue, "architecture": arch,
           "step": version, "@timestamp": rel_msec, "workflow": name,
           "hostname": hostname, "exit_code": exit_code}
  stats = json.load(open(sfile))
  average_stats = get_summary_stats_from_dictionary(stats, cpu_normalize)
  sdata.update(average_stats)
  if params: sdata.update(params)
  idx = sha1(release + arch + name + version + str(rel_sec)).hexdigest()
  try:send_payload(index+"-"+week,doc,idx,json.dumps(sdata))
  except Exception as e: print(e.message)

def es_send_external_stats(stats_dict, opts_dict, cpu_normalize=1, week='',
                           es_index_name='externals_stats_summary_testindex',
                           es_doc_name='externals-runtime-stats-summary-testdoc'):
  index_sha = sha1( ''.join([str(x) for x in opts_dict.values()])).hexdigest()
  sdata = get_summary_stats_from_dictionary(stats_dict, cpu_normalize)
  sdata.update(opts_dict)
  try:send_payload(es_index_name+"-"+week, es_doc_name, index_sha, json.dumps(sdata))
  except Exception as e: print(e.message)
