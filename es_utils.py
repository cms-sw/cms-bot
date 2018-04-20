#!/usr/bin/env python
import sys, urllib2, json, requests
from datetime import datetime
from time import time
from os.path import exists
from os import getenv

def resend_payload(hit, passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  return send_payload(hit["_index"], hit["_type"], hit["_id"],json.dumps(hit["_source"]),passwd_file)

def es_get_passwd(passwd_file=None):
  for psfile in [passwd_file, getenv("CMS_ES_SECRET_FILE",None), "/data/secrets/cmssdt-es-secret", "/build/secrets/cmssdt-es-secret", "/var/lib/jenkins/secrets/cmssdt-es-secret", "/data/secrets/github_hook_secret_cmsbot"]:
    if not psfile: continue
    if exists(psfile):
      passwd_file=psfile
      break
  try:
    return open(passwd_file,'r').read().strip()
  except Exception as e:
    print "Couldn't read the secrets file" , str(e)
    return ""

def send_payload_new(index, document, id, payload, es_server, passwd_file=None):
  index = 'cmssdt-' + index
  passwd=es_get_passwd(passwd_file)
  if not passwd: return False

  url = "https://%s/%s/%s/" % (es_server,index,document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'cmssdt', passwd)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "ERROR:",url,str(e)
    return False
  print "OK ",index
  return True

def send_payload_old(index,document,id,payload,passwd_file=None):
  passwd=es_get_passwd(passwd_file)
  if not passwd: return False

  url = "http://%s/%s/%s/" % ('cmses-master02.cern.ch:9200', index, document)
  if id: url = url+id
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'elasticsearch', passwd)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    content = urllib2.urlopen(url,payload)
  except Exception as e:
    print "ERROR: ",url, str(e)
    return False
  print "OK ",index
  return True

def delete_hit(hit,passwd_file=None):
  passwd=es_get_passwd(passwd_file)
  if not passwd: return False

  url = "http://%s/%s/%s/%s" % ('cmses-master02.cern.ch:9200',hit["_index"], hit["_type"], hit["_id"])
  passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
  passman.add_password(None,url, 'elasticsearch', passwd)
  auth_handler = urllib2.HTTPBasicAuthHandler(passman)
  opener = urllib2.build_opener(auth_handler)
  try:
    urllib2.install_opener(opener)
    request = urllib2.Request(url)
    request.get_method = lambda: 'DELETE'
    content = urllib2.urlopen(request)
  except Exception as e:
    print "ERROR: ",url, str(e)
    return False
  print "DELETE:",hit["_id"]
  return True

def send_payload(index,document,id,payload,passwd_file="/data/secrets/github_hook_secret_cmsbot"):
  send_payload_new(index,document,id,payload,'es-cmssdt.cern.ch:9203')
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

def get_payload_kerberos_exe(url, query):
  from commands import getstatusoutput as cmd
  e, o = cmd("eval `scram unset -sh`; python ./get_pl_krb.py '%s' '%s' 2>&1 | grep JSON_OUT= | sed 's|.*JSON_OUT= *||'" % (url, query))
  print e, o
  return json.loads(o)

def format(s, **kwds): return s % kwds

def es_query(index,query,start_time,end_time,page_start=0,page_size=100000,timestamp_field="@timestamp",lowercase_expanded_terms='false', es_host='http://cmses-master02.cern.ch:9200'):
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
  query_str = format(query_tmpl, query=query, start_time=start_time,end_time=end_time,page_start=page_start,page_size=page_size,timestamp_field=timestamp_field,lowercase_expanded_terms=lowercase_expanded_terms)
  print 'query url is ', query_url
  return json.loads(get_payload(query_url, query_str))

def es_krb_query(index,query,start_time,end_time,page_start=0,page_size=10000,timestamp_field="@timestamp",lowercase_expanded_terms='false', es_host='https://es-cmssdt.cern.ch/krb'):
  query_url='%s/%s/_search?scroll=1m' % (es_host, index)
  query_tmpl = """{
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "%(timestamp_field)s": {
              "gte": %(start_time)s,
              "lt":%(end_time)s
            }
          }
        }
      ],
      "must": {
        "query_string": {
          "query": "%(query)s"
        }
      }
    }
  },
  "from": %(page_start)s,
  "size": %(page_size)s
  }"""

  query_str = format(query_tmpl, query=query, start_time=start_time, end_time=end_time, page_start=page_start,
                     page_size=page_size, timestamp_field=timestamp_field, lowercase_expanded_terms=lowercase_expanded_terms)
  return get_payload_kerberos(query_url, query_str)

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

if __name__ == "__main__":

  query_url = 'https://es-cmssdt.cern.ch/krb/cmssdt-relvals_stats_summary*/_search?scroll=1m'
  query="""{
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "@timestamp": {
              "gte": "1522847085252"
            }
          }
        }
      ],
      "must": {
        "query_string": {
          "query": "release:/cmssw_10_2_clang.*/ AND architecture:/slc6_amd64_gcc630.*/ "
        }
      }
    }
  },
  "from": 0,
  "size": 10000
  }"""

  result = get_payload_kerberos_exe(query_url, query)
  with open('firstquery.json', "w") as firstquery:
        firstquery.write(json.dumps(result,indent=2, sort_keys=True, separators=(',', ': ')))
  exit(1)
  #for i in result:
  #    print i
  #print json.dumps(result, indent=2, sort_keys=True, separators=(',', ': '))
  '''
  query_url= 'http://cmses-master02.cern.ch:9200/relvals_stats_*/_search'
  query_datsets = """
      {
        "query": {
          "filtered": {
            "query": {
              "bool": {
                "should": [
                  {
                    "query_string": {
                      "query": "release:CMSSW_10_2_X* AND architecture:slc6_amd64_gcc630*", 
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
                        "gte": "1522241504472",
                        "lt": "1522327904472"
                      }
                    }
                  }
                ]
              }
            }
          }
        },
        "from": 0,
        "size": 10000
      }
      """
  '''
  #result = json.loads(get_payload(query_url, query_datsets))
  #with open('secondquery.json', "w") as secondquery:
  #      secondquery.write(json.dumps(result,indent=2, sort_keys=True, separators=(',', ': ')))
  #for i in result:
  #    print i

  #query_string = 'exit_code:0 AND release:CMSSW_10_2_CLANG* AND architecture:slc6_amd64_gcc630'
  #st = 1000*int(time()-(86400*10))
  #et = 1000*int(time())

  #result = es_query(index='relvals_stats_*', query=query_string, start_time=st,end_time= et)
  #for i in result:
  #    print i
  #print json.dumps(result, indent=2, sort_keys=True, separators=(',', ': '))

  query_string = 'release:/cmssw_10_2_clang.*/ AND architecture:/slc6_amd64_gcc630.*/ '
  result = es_krb_query(index='cmssdt-relvals_stats_summary*', query=query_string, start_time=st, end_time=et)
  print json.dumps(result, indent=2, sort_keys=True, separators=(',', ': '))
