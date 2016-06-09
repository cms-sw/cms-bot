#!/usr/bin/env python
from sys import exit
from datetime import datetime
from time import mktime
from es_utils import send_payload
from hashlib import sha1
from json import dumps
from logwatch import logwatch, run_cmd

def process (cmd):
  count = 0
  for line in run_cmd (cmd).split ("\n"):
    payload = {}
    items = line.split(" ")
    if len(items)<12: continue
    if not (items[3][0]=='[' and items[4][-1]==']'): continue
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
    if not send_payload("apache-cmsrep","access_log", id, dumps(payload), passwd_file="/data/es/es_secret"):
      exit(0)
    count = count + 1
    if count%1000==0:
      print "Processed ",count,"entries"
  print "Processed ",count,"entries"

count=run_cmd("pgrep -l -x -f '^python .*/es_cmsrep_apache.py$' | wc -l",False)
if int(count)>1: exit(0)
logs = run_cmd("ls -rt /var/log/httpd/access_log* | grep -v '[.]gz$'").split("\n")
log = logwatch("httpd",log_dir="/data/es")
for cmd in log.get_command(logs):
  print cmd[0]
  process(cmd[0])
  print cmd[1]
  run_cmd(cmd[1])

