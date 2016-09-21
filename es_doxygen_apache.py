#!/usr/bin/env python
import re
from sys import exit
from datetime import datetime
from time import mktime
from es_utils import send_payload
from hashlib import sha1
from json import dumps
from logwatch import logwatch, run_cmd, LOGWATCH_APACHE_IGNORE_AGENTS

def process (line, count):
  for agent in LOGWATCH_APACHE_IGNORE_AGENTS:
    if agent in line: return True
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
  payload["@timestamp"]=int(mktime(datetime.strptime(items[3][1:],'%d/%b/%Y:%H:%M:%S').timetuple())*1000)
  if len(items)>10: payload["referrer"]=items[10][1:-1]
  if len(items)>11 and re.match('^"[0-9]+(\.[0-9]+)+"$', items[11]):
    payload["ip"]=items[11][1:-1]
    if len(items)>12:
      agent  = " ".join(items[12:]).replace('"','')
      payload["agent"] = agent
      payload["agent_type"]=agent.replace(" ","-").split("/",1)[0].upper()
  id = sha1(line).hexdigest()
  if (count%1000)==0: print "Processed entries",count
  if not send_payload("apache-doxygen","access_log", id, dumps(payload), passwd_file="/data/es/es_secret"):
    return False
  return True

count=run_cmd("pgrep -l -x -f '^python .*/es_doxygen_apache.py$' | wc -l",False)
if int(count)>1: exit(0)
logs = run_cmd("ls -rt /var/log/httpd/access_log* | grep -v '[.]gz$'").split("\n")
log = logwatch("httpd",log_dir="/data/es")
s,c=log.process(logs, process)
print "Total entries processed",c

