#!/usr/bin/env python
from __future__ import print_function
import sys, json, re, ssl, base64
from os.path import exists
from os import getenv
from hashlib import sha1
from cmsutils import cmsswIB2Week, percentile
from _py2with3compatibility import Request, urlopen
from os import stat as tstat
from time import time

CMSSDT_ES_QUERY="https://cmssdt.cern.ch/SDT/cgi-bin/es_query"
#ES_SERVER = 'https://es-cmssdt7.cern.ch:9203'
ES_SERVER = 'https://es-cmssdt1.cern.ch/es'
ES_NEW_SERVER = ES_SERVER
ES_PASSWD = None
def format(s, **kwds): return s % kwds

def get_es_query(query="", start_time=0, end_time=0, page_start=0, page_size=10000, timestamp_field='@timestamp', lowercase_expanded_terms='false', fields=None):
  es5_query_tmpl="""
{
"_source": [%(fields_list)s],
"query": {
  "bool": {
    "must": [
      {"query_string": {"query": "%(query)s"}},
      {"range": {"%(timestamp_field)s": {"gte": %(start_time)s, "lte": %(end_time)s}}}
    ]
  }
},
"sort": [{"%(timestamp_field)s": "desc"}],
"from" : %(page_start)s,
"size" : %(page_size)s
}
"""
  if not fields: fields = ["*"]
  fields_list = ",".join([ '"%s"' % f for f in fields])
  return format(es5_query_tmpl, **locals ())

def get_ssl_context():
  sslcon = None
  try: sslcon = ssl._create_unverified_context()
  except Exception as e: sslcon =  None
  return sslcon

def ssl_urlopen(url, data):
  return urlopen(url, data, context=get_ssl_context()).read()

def resend_payload(hit):
  print("Resending ",hit)
  return send_payload(hit["_index"], "_doc", hit["_id"],json.dumps(hit["_source"]))

def es_get_passwd(passwd_file=None):
  global ES_PASSWD
  if ES_PASSWD: return ES_PASSWD
  for psfile in [passwd_file, getenv("CMS_ES_SECRET_FILE",None), "/data/secrets/cmssdt-es-secret", "/build/secrets/cmssdt-es-secret", "/var/lib/jenkins/secrets/cmssdt-es-secret", "/data/secrets/github_hook_secret_cmsbot"]:
    if not psfile: continue
    if exists(psfile):
      passwd_file=psfile
      break
  ES_PASSWD = open(passwd_file,'r').read().strip()
  return ES_PASSWD

def send_request(uri, payload=None, passwd_file=None, method=None, es_ser=ES_SERVER, ignore_doc=False, ignore_new=False):
  if (not ignore_new) and (ES_SERVER!=ES_NEW_SERVER) and (es_ser==ES_SERVER):
    if not send_request(uri, payload, passwd_file, method, es_ser=ES_NEW_SERVER, ignore_doc=ignore_doc):
      return False
  header = {"Content-Type": "application/json"}
  xuri = uri.split("/")
  if (not ignore_doc) and (xuri[1] != "_doc"):
    xuri[1] = "_doc"
    uri = "/".join(xuri)
  passwd=es_get_passwd(passwd_file)
  if not passwd: return False
  url = "%s/%s" % (es_ser,uri)
  if sys.version_info[0] == 2: 
    header['Authorization'] = 'Basic %s' % base64.b64encode("cmssdt:%s" % passwd)
  else:
    header['Authorization'] = 'Basic %s' % base64.b64encode(("cmssdt:%s" % passwd).encode()).decode() 
  try:
    if sys.version_info[0] == 2:
      request = Request(url, payload, header)
    else:
      request = Request(url, payload.encode(), header)
    if method: request.get_method = lambda: method
    content = urlopen(request, context=get_ssl_context())
  except Exception as e:
    print("ERROR:",url,str(e))
    print(payload)
    return False
  print("OK:",url)
  return True

def send_payload(index, document, id, payload, passwd_file=None):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  uri = "%s/%s/" % (index,document)
  if id: uri = uri+id
  return send_request(uri, payload=payload, method="POST", passwd_file=passwd_file)

def send_template(name, payload, passwd_file=None):
  if not name.startswith('cmssdt-'): name = 'cmssdt-' + name
  uri = "_template/%s" % name
  return send_request(uri, payload=payload, passwd_file=passwd_file, method='PUT', ignore_doc=True)

def delete_hit(hit,passwd_file=None):
  uri = "%s/%s/%s" % (hit["_index"], "_doc", hit["_id"])
  if not send_request(uri, passwd_file=passwd_file, method='DELETE'): return False
  print("DELETE:",hit["_id"])
  return True

def get_payload(index, query, scroll=0):
  data = {'index':index, 'query':query, 'scroll':scroll}
  if scroll<=1: data['params'] = 'ignore_unavailable=true'
  data["es_server"]=ES_SERVER
  return ssl_urlopen(CMSSDT_ES_QUERY,json.dumps(data).encode("ascii","ignore"))

def get_payload_wscroll(index, query, max_count=-1):
  es_data = json.loads(get_payload(index, query,scroll=1))
  if 'proxy-error' in es_data: return es_data
  es_data.pop("_shards", None)
  if type(es_data['hits']['total']) == int:
    scroll_size = es_data['hits']['total']
  else:
    scroll_size = es_data['hits']['total']['value']
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
  return ssl_urlopen(CMSSDT_ES_QUERY,json.dumps(data))

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
  data = {'index':index, 'api': '/_cat', 'prefix': True, 'method': 'GET'}
  return ssl_urlopen(CMSSDT_ES_QUERY,json.dumps(data))

def close_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/_close',method='POST', ignore_doc=True, ignore_new=True)

def open_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/_open',method='POST', ignore_doc=True, ignore_new=True)

def delete_index(index):
  if not index.startswith('cmssdt-'): index = 'cmssdt-' + index
  send_request(index+'/',method='DELETE', ignore_doc=True, ignore_new=True)

def es_query(index,query,start_time,end_time,page_start=0,page_size=10000,timestamp_field="@timestamp", scroll=False, max_count=-1, fields=None):
  query_str = get_es_query(query=query, start_time=start_time,end_time=end_time,page_start=page_start,page_size=page_size,timestamp_field=timestamp_field, fields=fields)
  if scroll: return get_payload_wscroll(index, query_str, max_count)
  return json.loads(get_payload(index, query_str))

def es_workflow_stats(es_hits,rss='rss_75', cpu='cpu_75'):
  wf_stats = {}
  for h in es_hits['hits']['hits']:
    hit = h["_source"]
    if 'time' not in hit: continue
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

def get_summary_stats_from_json_file(stats_dict_file_path, cpu_normalize):
  with open(stats_dict_file_path, 'r') as stas_d_f: stats_dict = json.load(stas_d_f)
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
  average_stats = get_summary_stats_from_json_file(sfile, cpu_normalize)
  sdata.update(average_stats)
  if params: sdata.update(params)
  idx = sha1(release + arch + name + version + str(rel_sec)).hexdigest()
  try:send_payload(index+"-"+week,doc,idx,json.dumps(sdata))
  except Exception as e: print(e.message)

def es_send_external_stats(stats_dict_file_path, opts_dict_file_path, cpu_normalize=1,
                           es_index_name='externals_stats_summary',
                           es_doc_name='externals-stats-summary'):
  file_stamp = int(tstat(stats_dict_file_path).st_mtime)  # get the file stamp from the file
  week = str((file_stamp / 86400 + 4) / 7)
  with open(opts_dict_file_path, 'r') as opts_dict_f: opts_dict = json.load(opts_dict_f)
  index_sha = sha1( ''.join([str(x) for x in opts_dict.values()])+stats_dict_file_path).hexdigest()
  sdata = get_summary_stats_from_json_file(stats_dict_file_path, cpu_normalize)
  sdata.update(opts_dict)
  sdata["@timestamp"]=file_stamp*1000
  try:send_payload(es_index_name+"-"+week, es_doc_name, index_sha, json.dumps(sdata))
  except Exception as e: print(e.message)

def getExternalsESstats(arch='*', externalsList='', lastNdays=30, page_size=0, fields=None):
  externals_names=''
  if externalsList == '':
    externals_names="*"
  else:
    externals_names= (" OR ").join(externalsList.split(','))
  stats = es_query(index='externals_stats_summary-*',
                   query=format('architecture:%(architecture)s AND name.keyword:(%(names)s)',
                                architecture=arch,
                                names=externals_names),
                   start_time=1000*int(time()-(86400*lastNdays)),
                   end_time=1000*int(time()),scroll=True, fields=fields)
  return stats['hits']['hits']

# get a dict of stats with externals name as keys
# create a default github file with stats so if elastic search fails,
def orderStatsByName(externalsStats=None):    
    namedStats = {}
    for element in externalsStats:
        ext_name = element["_source"]["name"]
        if ext_name not in namedStats:
            namedStats[ext_name] = list()
        namedStats[ext_name].append(element["_source"])
    # order by timestamp
    for ext in namedStats:
        namedStats[ext] = sorted(namedStats[ext], key=lambda x: x["@timestamp"], reverse=True)
    return namedStats

def get_externals_build_stats(arch='*', lastNdays=30, cpus=0, memoryGB=0, default_key="90"):
    default_keys= {"cpu": "cpu_" + default_key, "rss": "rss_" + default_key, "time": "time"}
    all_data = {}
    if cpus<=0:
        from cmsutils import MachineCPUCount
        cpus=MachineCPUCount
    if memoryGB<=0:
        from cmsutils import MachineMemoryGB, MachineCPUCount
        memoryGB = MachineMemoryGB
    mem=memoryGB*1024*1024*1024

    fields = list(default_keys.values()) + ["name", "build_jobs"]
    items = getExternalsESstats(arch=arch, lastNdays=lastNdays, fields=fields)
    for item in items:
        name=item['_source']['name']
        jobs=item['_source']['build_jobs']
        if name not in all_data:
            all_data[name] = {}
            for k in default_keys: all_data[name][k] = []
        for k in default_keys:
            xk = default_keys[k]
            all_data[name][k].append(int(item['_source'][xk]*cpus/jobs))

    default_res = 4
    if cpus<4: default_res=1
    elif cpus<8: default_res=2
    total_cpus = cpus*100
    data={"defaults": {"cpu": (50, total_cpus/default_res),
                       "rss": (int(mem/cpus), int(mem/default_res)),
                       "time": (1, 300)
                      },
          "resources":{"cpu": total_cpus, "rss": mem},
          "packages": {},
          "known": [("^.+-toolfile$", 0),
                    ("^data-.+$", 0),
                    ("^.+$", 1)]
         }
    for name in all_data:
        data["packages"][name] = {'cpu': 0, 'rss': 0, 'time': -1, "name": name}
        for k in default_keys:
            if all_data[name][k]:
                data["packages"][name][k] = int(sum(all_data[name][k])/len(all_data[name][k]))
        #Default resources if no data found for a package
        if data["packages"][name]['time']==-1:
            idx = 1
            for exp in data["known"]:
                if re.match(exp[0], name):
                    idx = exp[1]
                    break
            for k in data["defaults"]:
                data["packages"][name][k] = data["defaults"][k][idx]
        #for small package with build time 1 or less use min resources
        elif data["packages"][name]['time']==0:
            for k in data["defaults"]:
                data["packages"][name][k] = data["defaults"][k][0]
        else:
            #Make sure resources are not more than the total
            for k in data["defaults"]:
                if k == "time": continue
                v = data["packages"][name][k]
                if v>data["resources"][k]:
                    v = data["resources"][k]
                elif v==0:
                    v = data["defaults"][k][0]
                data["packages"][name][k] = v
    return data
