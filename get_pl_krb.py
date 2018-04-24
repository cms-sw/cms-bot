#!/usr/bin/env python
import requests, json
from requests_kerberos import HTTPKerberosAuth, DISABLED

class KerberosTicket:
  def __init__(self, service):
    __, krb_context = kerberos.authGSSClientInit(service)
    kerberos.authGSSClientStep(krb_context, "")
    self._krb_context = krb_context
    self.auth_header = ("Negotiate " +
                        kerberos.authGSSClientResponse(krb_context))
  def verify_response(self, auth_header):
    # Handle comma-separated lists of authentication fields
     for field in auth_header.split(","):
      kind, __, details = field.strip().partition(" ")
      if kind.lower() == "negotiate":
        auth_details = details.strip()
        break
      else:
        raise ValueError("Negotiate not found in %s" % auth_header)
      # Finish the Kerberos handshake
      krb_context = self._krb_context
      if krb_context is None:
        raise RuntimeError("Ticket already used for verification")
      self._krb_context = None
      kerberos.authGSSClientClean(krb_context)


def get_payload_kerberos(url, query):
  #short_url = url.split('/')[2]
  #krb = KerberosTicket("HTTP@"+short_url)
  #headers = {"Authorization": krb.auth_header}
  #r = requests.post(url, headers=headers, verify=False, data=query)
  kerb_auth = HTTPKerberosAuth(mutual_authentication=DISABLED)
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
  
  import sys
  result = get_payload_kerberos(sys.argv[1],sys.argv[2])
  print "JSON_OUT="+json.dumps(result)
