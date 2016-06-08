#!/usr/bin/env python
from os.path import exists, join
from sys import exit
from commands import getstatusoutput
from datetime import datetime
from time import mktime
from es_utils import send_payload
from hashlib import sha1
from json import dumps

def run_cmd (cmd, exit_on_error=True):
  err, out = getstatusoutput (cmd)
  if err and exit_on_error: exit (1)
  return out

def process (log, backup):
  cmd = "cat %s" % log
  if backup and exists(backup):
    out = run_cmd ("cat %s | wc -l" % backup)
    cmd = "tail -n +%s %s" % (out , log)
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
    payload["agent"]=" ".join(items[11:]).replace('"','').replace(" ","-")
    payload["@timestamp"]=int(mktime(datetime.strptime(items[3][1:],'%d/%b/%Y:%H:%M:%S').timetuple())*1000)
    id = sha1(line).hexdigest()
    send_payload("apache-cmsrep","access_log", id, dumps(payload), passwd_file="/data/es/es_secret")
    count = count + 1
    if count%1000==0:
      print "Processed ",count,"entries"
  print "Processed ",count,"entries"

count=run_cmd("pgrep -f /es_cmsrep_apache.py | wc -l ",False)
if int(count)>2: exit(0)
access_log = "access_log"
apache_dir = "/var/log/httpd"
backup_dir = "/data/es/http-log"
log_copy   = join (backup_dir, access_log)
tmp_log    = log_copy+".tmp"

cmd_to_get_logs = "ls -rt %s/%s* | tail -2" % (apache_dir, access_log)

logs = run_cmd (cmd_to_get_logs).split ("\n")
if len(logs)==0: exit(0)
if exists(log_copy):
  if len(logs)>1:
    out1 = run_cmd ("head -1 %s" % logs[-1])
    out2 = run_cmd ("head -1 %s" % log_copy)
    if out1 != out2: process (logs[-2], log_copy)
elif len(logs)>1:
  process(logs[-2], None)

out  = run_cmd ("touch %s && rsync %s %s" % (log_copy, logs[-1], tmp_log))
process(tmp_log, log_copy)
run_cmd ("mv -f %s %s" % (tmp_log , log_copy))

