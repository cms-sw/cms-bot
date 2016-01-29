#!/usr/bin/env python
import sys
import json
from os import environ
from os.path import exists
from RelValArgs import GetMatrixOptions
from runPyRelValThread import PyRelValsThread, splitWorkflows
from cmsutils import doCmd

workdir = sys.argv[1]
RelValtimes = sys.argv[2]
try:
  max_wf=int(sys.argv[3])
except:
  max_wf=100
relval_args = GetMatrixOptions(environ["CMSSW_VERSION"], environ["SCRAM_ARCH"])
matrix =  PyRelValsThread(1,environ["CMSSW_BASE"])
workflows = matrix.getWorkFlows(relval_args)
if exists(RelValtimes):
  owf = []
  max_tm=0
  with open(RelValtimes) as json_file:
    json_data = json.load(json_file)
    for tm_str in sorted(json_data["avg"],key=int, reverse=True):
      tm=int(tm_str)
      if tm > max_tm : max_tm=tm
      for wf in json_data["avg"][tm_str]:
        if wf in workflows: owf.append([wf,tm])
  uwf = []
  owfs = [ x[0] for x in owf ]
  for wf in workflows:
    if not wf in owfs: uwf.append([wf,max_tm])
  workflows = uwf + owf
if workflows:
  workflows = splitWorkflows(workflows, max_wf)
  print workflows
  total = len(workflows)
  for i in range(1, total+1):
    wf=",".join(workflows[i-1])
    jobid   = str(i)+"of"+str(total)
    jobfile = workdir+"/ib-run-relval-"+jobid
    doCmd("echo WORKFLOWS="+wf+" >"+jobfile)
    doCmd("echo JOBID="+jobid+" >>"+jobfile)
