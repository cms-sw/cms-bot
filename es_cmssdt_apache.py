#!/usr/bin/env python
from sys import exit
from datetime import datetime
from time import mktime
from es_utils import send_payload
from hashlib import sha1
from json import dumps
from logwatch import logwatch, run_cmd

def process (line, count):
  payload = {}
  items = line.split(" ")
  if len(items)<10: return True
  if not (items[3][0]=='[' and items[4][-1]==']'): return True
  payload["ip"]=items[0]
  payload["ident"]=items[1]
  payload["auth"]=items[2]
  payload["verb"]=items[5][1:]
  payload["request"]=items[6]
  payload["httpversion"]=items[7][:-1]
  payload["response"]=items[8]
  try:
    payload["bytes"]=int(items[9])
  except:
    payload["bytes"]=0
  payload["referrer"]="-"
  payload["agent"]="-"
  payload["agent_type"]="-"
  payload["@timestamp"]=int(mktime(datetime.strptime(items[3][1:],'%d/%b/%Y:%H:%M:%S').timetuple())*1000)
  id = sha1(line).hexdigest()
  if (count%1000)==0: print "Processed entries",count
  if not send_payload("apache-cmssdt","access_log", id, dumps(payload), passwd_file="/data/es/es_secret"):
    return False
  if payload["request"].startswith("/SDT/releases.map?release="):
    payload = dict(item.split("=") for item in payload["request"].split("?",1)[1].split("&"))
    return send_payload("scram-access","cmssw-releases", id, dumps(payload), passwd_file="/data/es/es_secret")
  return True

count=run_cmd("pgrep -l -x -f '^python .*/es_cmssdt_apache.py$' | wc -l",False)
if int(count)>1: exit(0)
logs = run_cmd("ls -rt /var/log/httpd/sdt-access_log* | grep -v '[.]gz$'").split("\n")
log = logwatch("httpd",log_dir="/data/es")
s,c=log.process(logs, process)
print "Total entries processed",c

