#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
import sys
import json
from os import environ
from os.path import exists
from RelValArgs import GetMatrixOptions
from runPyRelValThread import PyRelValsThread, splitWorkflows
from cmsutils import doCmd

print("Diving workflows")
workdir = sys.argv[1]
RelValtimes = sys.argv[2]
print(RelValtimes)
try:
    max_wf = int(sys.argv[3])
except:
    max_wf = 100
relval_args = GetMatrixOptions(environ["CMSSW_VERSION"], environ["SCRAM_ARCH"])
if "RELVAL_WORKFLOWS" in environ:
    relval_args = relval_args + " " + environ["RELVAL_WORKFLOWS"]
matrix = PyRelValsThread(1, environ["CMSSW_BASE"])
workflows = matrix.getWorkFlows(relval_args)
if exists(RelValtimes):
    owf = []
    max_tm = 0
    with open(RelValtimes) as json_file:
        try:
            json_data = json.load(json_file)
        except:
            print("Error reading RelVal Times")
            json_data = {"avg": []}
        for tm_str in sorted(json_data["avg"], key=int, reverse=True):
            tm = int(tm_str)
            if tm > max_tm:
                max_tm = tm
            for wf in json_data["avg"][tm_str]:
                if wf in workflows:
                    owf.append([wf, tm])
    uwf = []
    owfs = [x[0] for x in owf]
    for wf in workflows:
        if not wf in owfs:
            uwf.append([wf, max_tm])
    workflows = uwf + owf
if workflows:
    workflows = splitWorkflows(workflows, max_wf)
    print(workflows)
    on_grid = 0
    # if '_DEVEL_X' in environ['CMSSW_VERSION']:
    #  on_grid = 2
    total = len(workflows)
    try:
        for i in range(1, total + 1):
            wf = ",".join(workflows[i - 1])
            jobid = str(i) + "of" + str(total)
            jobfile = workdir + "/ib-run-relval-" + jobid
            doCmd("echo WORKFLOWS=" + wf + " >" + jobfile)
            doCmd("echo JOBID=" + jobid + " >>" + jobfile)
            if on_grid > 0:
                doCmd("echo 'SLAVE_LABELS=(condor&&cpu-8)' >>" + jobfile)
                on_grid = on_grid - 1
    except Exception as e:
        print("Error ", e)
