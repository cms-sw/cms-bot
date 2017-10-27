#! /usr/bin/env python
from sys import exit, argv
from optparse import OptionParser
from os import environ, system, waitpid
from runPyRelValThread import PyRelValsThread
from RelValArgs import GetMatrixOptions, isThreaded
from logUpdater import LogUpdater
from cmsutils import cmsRunProcessCount, MachineMemoryGB
from cmssw_known_errors import get_known_errors
from subprocess import Popen
from os.path import abspath, dirname
import re
SCRIPT_DIR = dirname(abspath(argv[0]))

def process_relvals(threads=None,cmssw_version=None,arch=None,cmssw_base=None,logger=None):
  pass

if __name__ == "__main__":
  parser = OptionParser(usage="%prog -i|--id <jobid> -l|--list <list of workflows>")
  parser.add_option("-i", "--id",   dest="jobid", help="Job Id e.g. 1of3", default="1of1")
  parser.add_option("-l", "--list", dest="workflow", help="List of workflows to run e.g. 1.0,2.0,3.0", type=str, default=None)
  parser.add_option("-f", "--force",dest="force", help="Force running of workflows without checking the server for previous run", action="store_true", default=False)
  opts, args = parser.parse_args()

  if len(args) > 0: parser.error("Too many/few arguments")
  if not opts.workflow: parser.error("Missing -l|--list <workflows> argument.")
  if (not environ.has_key("CMSSW_VERSION")) or (not environ.has_key("CMSSW_BASE")) or (not environ.has_key("SCRAM_ARCH")):
    print "ERROR: Unable to file the release environment, please make sure you have set the cmssw environment before calling this script"
    exit(1)
  
  thrds = cmsRunProcessCount
  cmssw_ver = environ["CMSSW_VERSION"]
  arch = environ["SCRAM_ARCH"]
  cmssw_base = environ["CMSSW_BASE"]
  logger=LogUpdater(dirIn=cmssw_base)
  
  if cmssw_ver.find('_XXXCLANG_') is not -1:
    p=Popen("python %s/rv_scheduler/prepareSteps.py -l %s" % (SCRIPT_DIR, opts.workflow),shell=True)
    e=waitpid(p.pid,0)[1]
    if e: exit(e)
    p=Popen("python %s/rv_scheduler/relval_main.py -a %s -r %s -d 7" % (SCRIPT_DIR, arch, cmssw_ver.rsplit('_',1)[0]), shell=True)
    e=waitpid(p.pid,0)[1]
    system("touch "+cmssw_base+"/done."+opts.jobid)
    if logger: logger.updateRelValMatrixPartialLogs(cmssw_base, "done."+opts.jobid)
    exit(e)
  
  if re.match("^CMSSW_(9_([3-9]|[1-9][0-9]+)|[1-9][0-9]+)_.*$",cmssw_ver):
    p=Popen("%s/jobs/create-relval-jobs.py %s" % (SCRIPT_DIR, opts.workflow),shell=True)
    e=waitpid(p.pid,0)[1]
    if e: exit(e)
    p = Popen("cd %s/pyRelval ; %s/jobs/jobscheduler.py -M 0 -c 175 -m 90 -o dynamic -t avg" % (cmssw_base,SCRIPT_DIR), shell=True)
    e=waitpid(p.pid,0)[1]
    system("touch "+cmssw_base+"/done."+opts.jobid)
    if logger: logger.updateRelValMatrixPartialLogs(cmssw_base, "done."+opts.jobid)
    exit(e)
  if isThreaded(cmssw_ver,arch):
    print "Threaded IB Found"
    thrds=int(MachineMemoryGB/4.5)
    if thrds==0: thrds=1
  elif "fc24_ppc64le_" in arch:
    print "FC22 IB Found"
    thrds=int(MachineMemoryGB/4)
  elif "fc24_ppc64le_" in arch:
    print "CentOS 7.2 + PPC64LE Found"
    thrds=int(MachineMemoryGB/3)
  else:
    print "Normal IB Found"
  if thrds>cmsRunProcessCount: thrds=cmsRunProcessCount
  known_errs = get_known_errors(cmssw_ver, arch, "relvals")
  matrix = PyRelValsThread(thrds, cmssw_base+"/pyRelval", opts.jobid)
  matrix.setArgs(GetMatrixOptions(cmssw_ver,arch))
  matrix.run_workflows(opts.workflow.split(","),logger,opts.force,known_errors=known_errs)
