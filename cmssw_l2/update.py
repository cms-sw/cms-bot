#!/usr/bin/env python3
import json,sys,os
from datetime import datetime,timedelta
sys.path.insert(0, os.getcwd())
try:
  from categories import CMSSW_L2
except:
  CMSSW_L2={}
try:
  from  categories import CMSSW_L1
except:
  CMSSW_L1= {}

l2_file = sys.argv[1]
ctime=int(int(sys.argv[2])/86400)*86400
data = {}
with open(l2_file) as ref:
  data=json.load(ref)

for u in CMSSW_L1:
  if u not in CMSSW_L2: CMSSW_L2[u]=['orp']
  else: CMSSW_L2[u].append('orp')

data_chg=False
stime = int(datetime.strptime('2000-01-01','%Y-%m-%d').strftime('%s'))
for u in CMSSW_L2:
  if u not in data:
    data[u] = [{'start_date': stime, 'category': []}]
    data_chg=True
  if (set(CMSSW_L2[u])!=set(data[u][-1]['category'])):
    if 'end_date' not in data[u][-1]:
      data[u][-1]['end_date'] = ctime
      data_chg=True
    if CMSSW_L2[u]:
      data[u].append({'start_date': ctime, 'category': CMSSW_L2[u]})
      data_chg=True

for u in data:
  if (u not in CMSSW_L2) and ('end_date' not in data[u][-1]):
    data[u][-1]['end_date'] = ctime
    data_chg=True

if data_chg:
  with open(l2_file, "w") as ref:
    json.dump(data, ref, sort_keys=True, indent=2)

