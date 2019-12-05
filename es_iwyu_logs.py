#!/bin/env python
from __future__ import print_function
import sys , json , os
from es_utils import send_payload
timestp = os.path.getmtime(sys.argv[1])
items = sys.argv[1].split('/')[:-1]
arch = items[-1]
rel = items[-2]
try:
  data = json.loads(open(sys.argv[1]).read().strip())
except:
  print('json file not found/processed')
payload = {}
payload['architecture'] = arch
payload['release'] = rel
payload['@timestamp'] = int(timestp*1000)
index = 'iwyu'
document = 'iwyu-stats'
id = False
for item in data:
  payload['package'] = item
  files , includes , excludes = data[item]
  payload['files'] = files
  payload['includes'] = includes
  payload['excludes'] = excludes
  payload['url'] = 'https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/iwyu/'+ arch + '/'+ rel + '/' + item + '/index.html'
  send_payload(index,document,id,json.dumps(payload))
