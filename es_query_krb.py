from get_pl_krb import get_payload_kerberos

query_tmpl = """{
  "query": {
    "bool": {
      "filter": [
        {
          "range": {
            "%(timestamp_field)s": {
              "gte": %(start_time)s,
              "lt": %(end_time)s
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
  "size": 10000
  }"""

def format(s, **kwds): return s % kwds

def es_krb_query(index,query,start_time,end_time,page_start=0,page_size=10000,timestamp_field="@timestamp",lowercase_expanded_terms='false', es_host='https://es-cmssdt.cern.ch/krb'):
  query_url='%s/%s/_search?scroll=1m' % (es_host, index)
  query_str = format(query_tmpl, query=query, start_time=start_time, end_time=end_time, page_start=page_start,
                     page_size=page_size, timestamp_field=timestamp_field, lowercase_expanded_terms=lowercase_expanded_terms)
  #print query_str
  return get_payload_kerberos(query_url, query_str)

if __name__ == "__main__":
  import sys, json
  #print sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4]
  result = es_krb_query(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4])
  print "JSON_OUT="+json.dumps(result)
