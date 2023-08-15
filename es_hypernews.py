#!/usr/bin/env python3
from __future__ import print_function
import sys, os, re
from datetime import datetime,timedelta
from _py2with3compatibility import run_cmd
from es_utils import send_payload
from hashlib import sha1
from json import dumps
from time import time

apache_log_dir="/var/log/httpd"
ssl_error_log = "ssl_error_log"
search_for=" Timeout waiting for output from CGI script "
filter_search = ""

process_all = False
files_to_process=[]
cmd_to_get_logs = "ls -rt "+os.path.join(apache_log_dir,ssl_error_log)+"*"
if len(sys.argv)==1:
  process_all = True
  cmd_to_get_logs = cmd_to_get_logs + " | tail -2"
  prev_hour = datetime.now()-timedelta(hours=1)
  filter_search = " | grep '"+prev_hour.strftime("^\[%a %b %d %H:[0-5][0-9]:[0-5][0-9] %Y\] ")+"'"

err, out = run_cmd(cmd_to_get_logs)
if err:
  print(out)
  sys.exit(1)
ReTime = re.compile('^\[[A-Za-z]{3} ([A-Za-z]{3} [0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9]{4})\] \[[^\]]+\] \[client (.+)\]\s(.+)')
for log in out.split("\n"):
  find_cmd = "grep '%s' %s %s" % (search_for, log, filter_search)
  err, out = run_cmd(find_cmd)
  for line in out.split("\n"):
    m = ReTime.match(line)
    if m:
      tsec = int(datetime.strptime(m.group(1), "%b %d %H:%M:%S %Y").strftime('%s'))
      week = str(int(tsec/(86400*7)))
      timestamp = tsec*1000
      payload = {}
      payload['@timestamp'] = timestamp
      payload['ip'] = m.group(2)
      payload['message'] = line
      id = sha1(str(timestamp)  + m.group(2)).hexdigest()
      send_payload("hypernews-"+week,"hn-timeouts",id, dumps(payload))
payload = {}
payload['@timestamp'] = int(time()*1000)
send_payload("hypernews","hn-heartbeat",str(payload['@timestamp']), dumps(payload))
