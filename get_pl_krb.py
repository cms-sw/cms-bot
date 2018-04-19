#!/usr/bin/env python
import sys, urllib2, json, requests, urllib3
from datetime import datetime
from time import time
from os.path import exists
from os import getenv
from requests_kerberos import HTTPKerberosAuth, REQUIRED

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_payload_kerberos(url, query):
  #short_url = url.split('/')[2]
  #krb = KerberosTicket("HTTP@"+short_url)
  #headers = {"Authorization": krb.auth_header}
  #r = requests.post(url, headers=headers, verify=False, data=query)
  kerb_auth = HTTPKerberosAuth(mutual_authentication=REQUIRED)
  r = requests.post(url, auth=kerb_auth, verify=False, data=query)
  es_data = json.loads(r.text)
  #print es_data
  scroll_url = 'https://es-cmssdt.cern.ch/krb/_search/scroll'
  scroll_size = es_data['hits']['total']
  final_scroll_data = es_data

  while (scroll_size > 0):
      scroll_id = es_data['_scroll_id']
      scroll_query = {"scroll_id": str(scroll_id), "scroll": "1m"}
      r= requests.post(scroll_url, auth=kerb_auth ,verify=False, data=json.dumps(scroll_query))
      es_data = json.loads(r.text)
      scroll_size = len(es_data['hits']['hits'])
      if (scroll_size > 0):
          final_scroll_data['hits']['hits'].append(es_data['hits']['hits'][0])

  #print json.dumps(final_scroll_data, indent=2, sort_keys=True, separators=(',', ': '))
  final_scroll_data = {'hits':final_scroll_data['hits'],'_shards':final_scroll_data['_shards'],'took':final_scroll_data['took'],'timed_out':final_scroll_data['timed_out']}
  return final_scroll_data

if __name__ == "__main__":
  
  result = get_payload_kerberos(sys.argv[1],sys.argv[2])
  print "JSON_OUT="+json.dumps(result)
  #with open('josnresult.json', 'w') as resfile:
  #  resultfile.write(json.dumps(result))
