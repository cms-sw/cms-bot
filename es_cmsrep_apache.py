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
  if len(items)<12: return True
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
  payload["referrer"]=items[10][1:-1] 
  agent = " ".join(items[11:]).replace('"','')
  if "CMSPKG-v" in agent: agent = agent.replace("-v","/")
  payload["agent"]=agent
  payload["agent_type"]=agent.replace(" ","-").split("/",1)[0].upper()
  payload["@timestamp"]=int(mktime(datetime.strptime(items[3][1:],'%d/%b/%Y:%H:%M:%S').timetuple())*1000)
  id = sha1(line).hexdigest()
  if (count%1000)==0: print "Processed entries",count
  if not send_payload("apache-cmsrep","access_log", id, dumps(payload), passwd_file="/data/es/es_secret"):
    return False
  if not payload["request"].startswith("/cgi-bin/cmspkg"): return True
  items = payload["request"].split("/")
  if len(items)<8: return True
  if items[3] != "RPMS": return True
  dev = 0
  if items[2].endswith('-dev'): dev=1
  xpayload = {}
  try:
    from urllib import unquote
    pkg, rest = items[7].split("?",1)
    cmspkg = rest.split("version=",1)[1].split("&",1)[0]
    xpayload = {'dev' : dev, 'repository' : items[4], 'architecture' : items[5], 'package' : unquote(pkg).split("-1-",1)[0], 'cmspkg' : cmspkg}
  except:
    return True
  for x in ["@timestamp","ip"]: xpayload[x] = payload[x]
  return send_payload("cmspkg-access","rpm-packages", id, dumps(xpayload), passwd_file="/data/es/es_secret")

count=run_cmd("pgrep -l -x -f '^python .*/es_cmsrep_apache.py$' | wc -l",False)
if int(count)>1: exit(0)
logs = run_cmd("ls -rt /var/log/httpd/access_log* | grep -v '[.]gz$'").split("\n")
log = logwatch("httpd",log_dir="/data/es")
s,c=log.process(logs, process)
print "Total entries processed",c

