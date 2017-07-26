#!/usr/bin/env python
import sys, json, glob, os
from commands import getstatusoutput
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CMS_BOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0,CMS_BOT_DIR)
sys.path.insert(0,SCRIPT_DIR)
from cmssw_known_errors import get_known_errors
from logUpdater import LogUpdater

def update_cmdlog(workflow_dir, jobs):
  workflow_cmdlog=os.path.join(workflow_dir,"cmdLog")
  if not os.path.exists(workflow_cmdlog): return
  wfile=open(workflow_cmdlog,"a")
  for job in jobs["commands"]:
    if job["exit_code"]>=0:
      wfile.write("\n# in: /some/build/directory going to execute ")
      for cmd in job["command"].split(";"):
        if cmd: wfile.write(cmd+"\n")
  wfile.close()
  return

def update_worklog(workflow_dir, jobs):
  workflow_logfile=os.path.join(workflow_dir,"workflow.log")
  if not os.path.exists(workflow_logfile): return False
  workflow_time=0
  exit_codes=""
  test_passed=""
  test_failed=""
  das_log = os.path.join(workflow_dir,"step1_dasquery.log")
  if os.path.exists(das_log):
    workflow_id = os.path.basename(workflow_dir).split("_",1)[1]
    getstatusoutput("cp %s %s/step1_%s.log" % (das_log, workflow_dir, workflow_id))
    e, o = getstatusoutput("grep ' tests passed' %s | grep '^1 ' | wc -l" % workflow_logfile)
    if o=="0": return False
    exit_codes="0"
    test_passed="1"
    test_failed="0"
  failed=False
  steps_res=[]
  for job in jobs["commands"]:
    if job["exit_code"]==-1: failed=True
    if job["exit_code"]>0:
      exit_codes+=" "+str(job["exit_code"])
      test_passed+=" 0"
      test_failed+=" 1"
      failed=True
      steps_res.append("FAILED")
    else:
      exit_codes+=" 0"
      test_failed+=" 0"
      if failed: test_passed+=" 0"
      else: test_passed+=" 1"
      steps_res.append("NORUN" if failed else "PASSED")
  step_str = ""
  for step, res in enumerate(steps_res): step_str = "%s Step%s-%s" % (step_str, step, res)
  e, o = getstatusoutput("grep ' exit: ' %s | sed 's|exit:.*$|exit: %s|'" % (workflow_logfile, exit_codes.strip()))
  o = re.sub("\s+Step0-.+\s+-\s+time\s+",step_str+"  - time ",o)
  wfile = open(workflow_logfile,"w")
  wfile.write(o+"\n")
  wfile.write("%s tests passed, %s failed\n" % (test_passed.strip(), test_failed.strip()))
  wfile.close()
  return True

def update_timelog(workflow_dir, jobs):
  workflow_time=os.path.join(workflow_dir,"time.log")
  wf_time=1
  for job in jobs["commands"]:
    if job["state"]=="Done": wf_time+=job["exec_time"]
  wfile = open(workflow_time,"w")
  wfile.write("%s\n" % wf_time)
  wfile.close()

def update_hostname(workflow_dir): getstatusoutput("hostname > %s/hostname" % workflow_dir)

def update_known_error(worflow, workflow_dir):
  known_errors = get_known_errors(os.environ["CMSSW_VERSION"], os.environ["SCRAM_ARCH"], "relvals")
  if worflow in known_errors:
    json.dump(known_errors[workflow], open("%s/known_error.json" % workflow_dir,"w"))
  return

def upload_logs(workflow, workflow_dir):
  basedir = os.path.dirname(workflow_dir)
  getstatusoutput("rm -f %s/*.root %s/core.*" % (workflow_dir,workflow_dir))
  final_log = os.path.join(basedir, workflow+"-final.log")
  if os.path.exists(final_log): getstatusoutput("mv %s %s/final.log" % (final_log, workflow_dir))
  logger=LogUpdater(dirIn=os.environ["CMSSW_BASE"], dryRun=True)
  logger.updateRelValMatrixPartialLogs(basedir, os.path.basename(workflow_dir))
  
jobs=json.load(open(sys.argv[1]))
workflow = jobs["name"]
workflow_dir=os.path.abspath(glob.glob("%s_*" % workflow)[0])
getstatusoutput("mv %s %s/job.json" % (sys.argv[1], workflow_dir))
if update_worklog(workflow_dir, jobs):
  update_cmdlog(workflow_dir, jobs)
update_timelog(workflow_dir, jobs)
update_hostname(workflow_dir)
update_known_error(workflow, workflow_dir)
upload_logs(workflow, workflow_dir)

