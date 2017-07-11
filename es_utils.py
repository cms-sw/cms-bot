#!/usr/bin/env python
import sys,urllib2 , json
from datetime import datetime
#Function to store data in elasticsearch

def resend_payload(hit, passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  return send_payload(hit["_index"], hit["_type"], hit["_id"],json.dumps(hit["_source"]),passwd_file)

def send_payload_new(index,document,id,payload,es_server,passwd_file="/data/secrets/cmssdt-es-secret"):
  index = 'cmssdt-' + index
  try:
    passw=open(passwd_file,'r').read().strip()
  except Exception as e:
    print "Couldn't read the secrets file" , str(e)

  url = "https://%s/%s/%s/" % (es_server,index,document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'cmssdt', passw)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    return False
  return True

def send_payload_old(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  try:
    passw=open(passwd_file,'r').read().strip()
  except Exception as e:
    print "Couldn't read the secrets file" , str(e)

  url = "http://%s/%s/%s/" % ('cmses-master01.cern.ch:9200',index,document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'elasticsearch', passw)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    return False
  return True

def send_payload(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  #send_payload_new(index,document,id,payload,'es-cmssdt.cern.ch:9203')
  send_payload_new(index,document,id,payload,'es-cmssdt5.cern.ch:9203')
  return send_payload_old(index,document,id,payload,passwd_file) 

def get_payload(url,query):
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'kibana', 'kibana')
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,query)
    return content.read()
  except Exception as e:
    print "Couldn't send data to elastic search" , str(e)
    return ""

def format(s, **kwds): return s % kwds
def es_query(index,query,start_time,end_time,page_start=0,page_size=100000,timestamp_field="@timestamp",lowercase_expanded_terms='false', es_host='http://cmses-master01.cern.ch:9200'):
  query_url='%s/%s/_search' % (es_host, index)
  query_tmpl = """{
  "query": {
      "filtered": {
        "query":  {"bool": {"should": [{"query_string": {"query": "%(query)s","lowercase_expanded_terms": %(lowercase_expanded_terms)s}}]}},
        "filter": {"bool": {"must":   [{"range": {"%(timestamp_field)s": {"from": %(start_time)s,"to": %(end_time)s}}}]}}
      }
    },
    "from": %(page_start)s,
    "size": %(page_size)s
  }"""
  query_str = format(query_tmpl, query=query,start_time=start_time,end_time=end_time,page_start=page_start,page_size=page_size,timestamp_field=timestamp_field,lowercase_expanded_terms=lowercase_expanded_terms)
  return json.loads(get_payload(query_url, query_str))

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
      if rss_v<1024: rss_v = int(sum([h[3] for h in hits])/thits)
      if cpu_v<10: cpu_v = int(sum([h[4] for h in hits])/thits)
      wf_stats[wf][step] = { "time" : time_v, "rss" : rss_v, "cpu" : cpu_v }
  return wf_stats
