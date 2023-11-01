#!/usr/bin/env python

# A script which creates a new index using a new mapping and create an alias
# for the old index name.

from __future__ import print_function
from _py2with3compatibility import run_cmd, Request, HTTPSHandler, build_opener, install_opener
from argparse import ArgumentParser
import json
import base64
from os import getenv
# Avoid checking for certificate since we execute this only inside CERN.
# Drop the following stanza if not.
import ssl
if hasattr(ssl, '_create_unverified_context'):
  ssl._create_default_https_context = ssl._create_unverified_context

def format(s, **kwds):
  return s % kwds

def writeToES(server, data):
  url = format("%(server)s/_bulk", server=server)
  handler= HTTPSHandler(debuglevel=0)
  opener = build_opener(handler)
  install_opener(opener)

  new_request = Request(url, data)
  new_request.get_method = lambda : "PUT"
  base64string = base64.encodestring(getenv("ES_AUTH")).replace('\n', '')
  new_request.add_header("Authorization", "Basic %s" % base64string)
  try:
    response = opener.open(new_request)
    print(response.read())
  except Exception as e:
    print(e)
    exit(1)

# - Get the index via scan and scroll.
# - Push items to the new index.
# - Delete old index.
# - Create alias from the old index to the new one.
if __name__ == "__main__":
  # First get all the available indices
  parser = ArgumentParser()
  parser.add_argument("--server", "-s", dest="server", 
                      default="localhost:9200", help="the elasticsearch server")
  parser.add_argument("--dry-run", "-n", dest="dryrun", action="store_true", 
                      default=False, help="do not change the DB.")
  parser.add_argument("source")
  parser.add_argument("dest")
  args = parser.parse_args()
  proxy_string = ""

  if not getenv("ES_AUTH"):
    print("ES_AUTH not specified")
    exit(1)

  user_string = "--user %s" % getenv("ES_AUTH")

  query = {
    "query": { "match_all": {}},
    "size":  1000
  }
  cmd = format("curl -s %(user_string)s '%(server)s/%(source)s/_search?search_type=scan&scroll=1m' -d'%(query)s'",
               source=args.source,
               query=json.dumps(query),
               server=args.server,
               user_string=user_string)
  print(cmd)
  err, out = run_cmd(cmd)
  if err:
    print("Error while getting indices")
    print(out)
    exit(0)
  result = json.loads(out)

  while True:
    cmd = format("curl -s %(user_string)s '%(server)s/_search/scroll?scroll=1m' -d'%(scroll_id)s'",
                 source=args.source,
                 query=json.dumps(query),
                 server=args.server,
                 user_string=user_string,
                 scroll_id=result["_scroll_id"])
    err, out = run_cmd(cmd)
    if err:
      print("Error while getting entries")
      print(out)
      exit(1)
    result = json.loads(out)
    if result.get("status", 200) != 200:
      print(out)
      exit(1)
    
    # Exit when there are not results
    if not len(result["hits"]["hits"]):
      break
    line = ""
    for item in result["hits"]["hits"]:
      cmd = format('{ "create": { "_index": "%(index)s", "_type": "%(obj_type)s", "_id": "%(obj_id)s" }}',
                   index=args.dest,
                   obj_type=item["_type"],
                   obj_id=item["_id"]
                  )
      payload = json.dumps(item["_source"])
      line += cmd+"\n"+payload + "\n"
      if len(line) < 500000:
        continue
    #  print json.dumps(json.loads(cmd))
    #  print json.dumps(json.loads(payload))
      writeToES(server=args.server, data=line)
      line = ""
    if line:
      writeToES(server=args.server, data=line)
