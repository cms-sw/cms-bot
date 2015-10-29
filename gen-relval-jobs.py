#!/usr/bin/env python
import sys
from os import environ
from RelValArgs import GetMatrixOptions
from runPyRelValThread import PyRelValsThread, splitWorkflows
from cmsutils import doCmd

workdir = sys.argv[1]
relval_args = GetMatrixOptions(environ["CMSSW_VERSION"], environ["SCRAM_ARCH"])
matrix =  PyRelValsThread(1,environ["CMSSW_BASE"])
workflows = matrix.getWorkFlows(relval_args)
if workflows:
  workflows = splitWorkflows(workflows, 100)
  print workflows
  total = len(workflows)
  for i in range(1, total+1):
    wf=",".join(workflows[i-1])
    jobid   = str(i)+"of"+str(total)
    jobfile = workdir+"/ib-test-relval-"+jobid
    doCmd("cp "+workdir+"/ib-test-qa "+jobfile)
    doCmd("echo WORKFLOWS="+wf+" >>"+jobfile)
    doCmd("echo JOBID="+jobid+" >>"+jobfile)
