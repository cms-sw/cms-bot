#!/usr/bin/env python
import os, sys
from operator import itemgetter
from time import time
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CMS_BOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0,CMS_BOT_DIR)
sys.path.insert(0,SCRIPT_DIR)
from es_utils import es_query, es_workflow_stats,format

def splitWorkflows(workflows, max_wf_pre_set):
  avg_t = sum ([ x[1] for x in workflows ] ) / len(workflows)
  wf_max = len(workflows)
  wf_pre_set = wf_max
  wf_sets = 1
  while (wf_pre_set > max_wf_pre_set):
    wf_sets=wf_sets+1
    wf_pre_set = int(wf_max/wf_sets)
  long_wf=int(wf_pre_set/2)
  short_wf=wf_pre_set-long_wf
  print len(workflows),avg_t,wf_sets,wf_pre_set,long_wf,short_wf
  merged = []
  for i in range (1, wf_sets):
    wf_count = len(workflows)
    sub_set=workflows[0:long_wf]+workflows[-short_wf:]
    new_avg = sum([ x[1] for x in sub_set])/len(sub_set)
    new_index=0
    while (new_avg > avg_t) and (new_index<long_wf):
       new_index+=1
       sub_set=workflows[0:long_wf-new_index]+workflows[-short_wf-new_index:]
       new_avg= sum([ x[1] for x in sub_set ])/len(sub_set)
    merged.append([x[0] for x in sub_set])
    workflows = workflows[long_wf-new_index:wf_count-short_wf-new_index]
  new_avg = sum([ x[1] for x in workflows])/len(workflows)
  merged.append([x[0] for x in workflows])
  return merged

queryInfo={"architecture": "slc6_amd64_gcc530", "release_cycle": "CMSSW_9_3_X_*",  "workflows": ""}
workflows = []
wfs=[]

for wf in [w for w in sys.argv[1].split(",") if w]: wfs.append(wf)
while wfs:
  queryInfo["workflows"] = " OR ".join(wfs[0:50])
  wfs = wfs[50:]
  wf_hits = es_query(index='relvals_stats_*',
                 query=format('release:%(release_cycle)s AND architecture:%(architecture)s AND (%(workflows)s)', **queryInfo),
                 start_time=int(time()*1000)-int(86400*1000*7),
                 end_time=int(time()*1000))
  stats = es_workflow_stats(wf_hits)
  for wf in stats:
    wf_weight = 0
    for step in stats[wf]:
      stat = stats[wf][step]
      wf_weight+=stat["cpu"]
    workflows.append({"workflow":wf, "weight": wf_weight})
order_workflows = []
for item in sorted(workflows,key=itemgetter("weight"),reverse=True):
  order_workflows.append([item["workflow"], item["weight"]])

wfs = []
for x in splitWorkflows(order_workflows,100): wfs.append(x)

wf_count=len(wfs)
for i in range(wf_count):
  xref=open("wf%sof%s.list" % (i+1, wf_count), "w")
  xref.write("%s\n" % ",".join(wfs[i]))
  xref.close()

