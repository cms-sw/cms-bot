#! /usr/bin/env python
from sys import exit
import sys
from optparse import OptionParser
from os import environ
import os
from shutil import copyfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CMS_BOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR,'..'))
sys.path.insert(0, CMS_BOT_DIR)

from runPyRelValThread import PyRelValsThread
from RelValArgs import GetMatrixOptions, isThreaded, FixWFArgs
from logUpdater import LogUpdater
from cmsutils import cmsRunProcessCount, MachineMemoryGB, doCmd
from cmssw_known_errors import get_known_errors


def runStep1Only(basedir, workflow, args=''):
  args = FixWFArgs (os.environ["CMSSW_VERSION"],os.environ["SCRAM_ARCH"],workflow,args)


  workdir = os.path.join(basedir, workflow)
  matrixCmd = 'runTheMatrix.py --maxSteps=0 -l ' + workflow +' '+args
  try:
    if not os.path.isdir(basedir):
      os.makedirs(basedir)
  except Exception, e:
    print "runPyRelVal> ERROR during test PyReleaseValidation steps, workflow "+str(workflow)+" : can't create thread folder: " + str(e)
  try:
    ret = doCmd(matrixCmd, False, basedir)
  except Exception, e:
    print "runPyRelVal> ERROR during test PyReleaseValidation steps, workflow "+str(workflow)+" : caught exception: " + str(e)
  return

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
  matrix = PyRelValsThread(thrds, environ["CMSSW_BASE"]+"/pyRelval", opts.jobid)
  matrix.setArgs(GetMatrixOptions(cmssw_ver,arch))
  #print matrix.args
  
  #print GetMatrixOptions(cmssw_ver,arch)
  #print matrix.args['rest']
  
  wfs = opts.workflow.split(",")
  
  for wf in wfs:
    print 'flow is :', wf
    #matrix.args['rest'] = FixWFArgs(cmssw_ver,arch,wf,matrix.args['rest']).replace(' -t 4','')
    #print fixed_args
    #matrix.args['rest'] = fixed_args.replace(' -t 4','')
    #print matrix.args['rest']
    #print matrix.args['w']
    runStep1Only(matrix.basedir, wf, matrix.args['rest']+" "+matrix.args['w'])
    wf_folder = [f for f in os.listdir(matrix.basedir) if f.find(wf+'_') is not -1][0]
    #print 'wf is:', wf, 'folder is', os.path.join(matrix.basedir,wf_folder)
    copyfile(os.path.join(matrix.basedir,'runall-report-step123-.log'),os.path.join(matrix.basedir,wf_folder,'workflow.log'))
    
    
  
  #print matrix.args['w']
  #runStep1Only(matrix.basedir, matrix.args['rest']+" "+matrix.args['w'])
  #
  #matrix.run_workflows(opts.workflow.split(","),LogUpdater(environ["CMSSW_BASE"]),opts.force,known_errors=known_errs)
  #matrix.getWorkflowSteps(opts.workflow)
