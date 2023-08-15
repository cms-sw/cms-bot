#!/usr/bin/env python3
from __future__ import print_function
from cmsutils import MachineMemoryGB, MachineCPUCount
import json, re, sys
r=open(sys.argv[1])
items=json.load(r)
r.close()
cpus=MachineCPUCount
mem=MachineMemoryGB*1024*1024*1024
default_keys= {"cpu": "cpu_90", "rss": "rss_90", "time": "time"}
all_data = {}
for item in items:
  name=item['_source']['name']
  jobs=item['_source']['build_jobs']
  if name not in all_data:
    all_data[name] = {}
    for k in default_keys: all_data[name][k] = []
  for k in default_keys:
    xk = default_keys[k]
    all_data[name][k].append(int(item['_source'][xk]*cpus/jobs))

default_res = 4
if cpus<4: default_res=1
elif cpus<8: default_res=2
else: default_res = 4
total_cpus = cpus*100
data={"defaults": {"cpu": (50, total_cpus/default_res),
                   "rss": (int(mem/cpus), int(mem/default_res)),
                   "time": (1, 300)
                  },
      "resources":{"cpu": total_cpus, "rss": mem},
      "packages": {},
      "known": [("^.+-toolfile$", 0),
                ("^data-.+$", 0),
                ("^.+$", 1)]
     }

for name in all_data:
  data["packages"][name] = {'cpu': 0, 'rss': 0, 'time': -1, "name": name}
  for k in default_keys:
    if all_data[name][k]:
      data["packages"][name][k] = int(sum(all_data[name][k])/len(all_data[name][k]))
  #Default resources if no data found for a package
  if data["packages"][name]['time']==-1:
    idx = 1
    for exp in data["known"]:
      if re.match(exp[0], name):
        idx = exp[1]
        break
    for k in data["defaults"]:
      data["packages"][name][k] = data["defaults"][k][idx]
  #for small package with build time 1 or less use min resources
  elif data["packages"][name]['time']==0:
    for k in data["defaults"]:
      data["packages"][name][k] = data["defaults"][k][0]
  else:
    #Make sure resources are not more than the total
    for k in data["defaults"]:
      if k == "time": continue
      v = data["packages"][name][k]
      if v>data["resources"][k]:
         v = data["resources"][k]
      elif v==0:
        v = data["defaults"][k][0]
      data["packages"][name][k] = v
print(json.dumps(data, sort_keys=True, indent=2))
