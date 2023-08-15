#! /usr/bin/env python3
from __future__ import print_function
import os, glob, re, shutil, time, threading
from cmsutils import doCmd
from es_relval_log import es_parse_log
from RelValArgs import FixWFArgs
from _py2with3compatibility import run_cmd
import json
from logreaderUtils import transform_and_write_config_file, add_exception_to_config

def runStep1Only(basedir, workflow, args=''):
  args = FixWFArgs (os.environ["CMSSW_VERSION"],os.environ["SCRAM_ARCH"],workflow,args)
  workdir = os.path.join(basedir, workflow)
  matrixCmd = 'runTheMatrix.py --maxSteps=0 -l ' + workflow +' '+args
  try:
    if not os.path.isdir(workdir):
      os.makedirs(workdir)
  except Exception as e:
    print("runPyRelVal> ERROR during test PyReleaseValidation steps, workflow "+str(workflow)+" : can't create thread folder: " + str(e))
  try:
    ret = doCmd(matrixCmd, False, workdir)
  except Exception as e:
    print("runPyRelVal> ERROR during test PyReleaseValidation steps, workflow "+str(workflow)+" : caught exception: " + str(e))
  return

def runThreadMatrix(basedir, workflow, args='', logger=None, wf_err={}):
  args = FixWFArgs (os.environ["CMSSW_VERSION"],os.environ["SCRAM_ARCH"],workflow,args)
  workdir = os.path.join(basedir, workflow)
  matrixCmd = 'runTheMatrix.py -l ' + workflow +' '+args
  try:
    if not os.path.isdir(workdir):
      os.makedirs(workdir)
  except Exception as e: 
    print("runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : can't create thread folder: " + str(e))
  wftime = time.time()
  try:
    ret = doCmd(matrixCmd, False, workdir)
  except Exception as e:
    print("runPyRelVal> ERROR during test PyReleaseValidation, workflow "+str(workflow)+" : caught exception: " + str(e))
  wftime = time.time() - wftime
  outfolders = [file for file in os.listdir(workdir) if re.match("^" + str(workflow) + "_", file)]
  if len(outfolders)==0: return
  outfolder = os.path.join(basedir,outfolders[0])
  wfdir     = os.path.join(workdir,outfolders[0])
  ret = doCmd("rm -rf " + outfolder + "; mkdir -p " + outfolder)
  ret = doCmd("find . -mindepth 1 -maxdepth 1 -name '*.xml' -o -name '*.log' -o -name '*.py' -o -name '*.json' -o -name 'cmdLog' -type f | xargs -i mv '{}' "+outfolder+"/", False, wfdir)
  logRE = re.compile('^(.*/[0-9]+(\.[0-9]+|)_([^/]+))/step1_dasquery.log$')
  for logFile in glob.glob(outfolder+"/step1_dasquery.log"):
    m = logRE.match(logFile)
    if not m : continue
    ret = doCmd ("cp "+logFile+" "+m.group(1)+"/step1_"+m.group(3)+".log")
  ret = doCmd("mv "+os.path.join(workdir,"runall-report-step*.log")+" "+os.path.join(outfolder,"workflow.log"))
  ret = doCmd("echo " + str(wftime) +" > " + os.path.join(outfolder,"time.log"))
  ret = doCmd("hostname -s > " + os.path.join(outfolder,"hostname"))
  if wf_err: json.dump(wf_err, open("%s/known_error.json" % outfolder,"w"))
  if logger: logger.updateRelValMatrixPartialLogs(basedir, outfolders[0])
  shutil.rmtree(workdir)
  return

def find_argv(args, arg):
  val=""
  fullval = ""
  reX = re.compile('\s*(('+arg+')(\s+|=)([^ ]+))')
  m=reX.search(args)
  if m: glen = len(m.groups())
  while m:
    fullval = m.group(1)
    val = m.group(glen)
    args = args.replace(fullval,"")
    m=reX.search(args)
  return (args, fullval, val)

def splitWorkflows(workflows, max_wf_pre_set):
  print(workflows)
  avg_t = sum ([ x[1] for x in workflows ] ) / len(workflows)
  wf_max = len(workflows)
  wf_pre_set = wf_max
  wf_sets = 1
  while (wf_pre_set > max_wf_pre_set):
    wf_sets=wf_sets+1
    wf_pre_set = int(wf_max/wf_sets)
  long_wf=int(wf_pre_set/2)
  short_wf=wf_pre_set-long_wf
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
  merged.append([x[0] for x in workflows])
  return merged

class PyRelValsThread(object):
  def __init__(self, jobs, basedir, jobid="1of1", outdir=None):
    if not outdir: outdir = basedir
    self.jobs = jobs
    self.basedir = basedir
    self.jobid=jobid
    self.outdir = outdir
    self.args = {}
    self.setArgs("")

  def setArgs(self, args):
    args = args.replace('\\"','"')
    args, self.args['w'], tmp = find_argv(args,"-w|--what")
    args, self.args['l'], tmp = find_argv(args,"-l|--list")
    args, self.args['j'], tmp = find_argv(args,"-j|--nproc")
    if ' -s ' in args:
      self.args['s']='-s'
      args = args.replace(' -s ','')
    else: self.args['s']= ""
    self.args['rest'] = args

  def getWorkFlows(self, args):
    self.setArgs(args)
    workflowsCmd = "runTheMatrix.py -n "+self.args['w']+" "+self.args['s']+" "+self.args['l']+" |  grep -v ' workflows with ' | grep -E '^[0-9][0-9]*(\.[0-9][0-9]*|)\s\s*' | sort -nr | awk '{print $1}'"
    print("RunTheMatrix>>",workflowsCmd)
    cmsstat, workflows = doCmd(workflowsCmd)
    if not cmsstat:
      return workflows.split("\n")
    print("runPyRelVal> ERROR during test PyReleaseValidation : could not get output of " + workflowsCmd)
    return []

  def isNewRunTheMatrix(self):
    e, o = doCmd("runTheMatrix.py --help | grep 'maxSteps=MAXSTEPS' | wc -l")
    if e: return False
    return o=="1"

  def getWorkflowSteps(self, workflows):
    threads = []
    while(len(workflows) > 0):
      threads = [t for t in threads if t.is_alive()]
      if(len(threads) < self.jobs):
        try:
          t = threading.Thread(target=runStep1Only, args=(self.basedir, workflows.pop(), self.args['rest']+" "+self.args['w']))
          t.start()
          threads.append(t)
        except Exception as e:
          print("runPyRelVal> ERROR threading matrix step1 : caught exception: " + str(e))
    for t in threads: t.join()
    return

  def run_workflows(self, workflows=[], logger=None, known_errors={}):
    if not workflows: return
    workflows = workflows[::-1]
    threads = []
    while(len(workflows) > 0):
      threads = [t for t in threads if t.is_alive()]
      if(len(threads) < self.jobs):
        try:
          wf = workflows.pop()
          wf_err = {}
          if wf in known_errors: wf_err = known_errors[wf]
          t = threading.Thread(target=runThreadMatrix, args=(self.basedir, wf, self.args['rest']+" "+self.args['w'], logger, wf_err))
          t.start()
          threads.append(t)
        except Exception as e:
          print("runPyRelVal> ERROR threading matrix : caught exception: " + str(e))
      else:
        time.sleep(5)
    for t in threads: t.join()
    ret, out = doCmd("touch "+self.basedir+"/done."+self.jobid)
    if logger: logger.updateRelValMatrixPartialLogs(self.basedir, "done."+self.jobid)
    return
  
  def update_runall(self):
    self.update_known_errors()
    runall = os.path.join(self.outdir,"runall-report-step123-.log")
    outFile    = open(runall+".tmp","w")
    status_ok  = []
    status_err = []
    len_ok  = 0
    len_err = 0
    for logFile in glob.glob(self.basedir+'/*/workflow.log'):
      inFile = open(logFile)
      for line in inFile:
        if re.match("^\s*(\d+\s+)+tests passed,\s+(\d+\s+)+failed\s*$",line):
          res = line.strip().split(" tests passed, ")
          res[0] = res[0].split()
          res[1]=res[1].replace(" failed","").split()
          len_res = len(res[0])
          if len_res>len_ok:
            for i in range(len_ok,len_res): status_ok.append(0)
            len_ok = len_res
          for i in range(0,len_res):
            status_ok[i]=status_ok[i]+int(res[0][i])
          len_res = len(res[1])
          if len_res>len_err:
            for i in range(len_err,len_res): status_err.append(0)
            len_err = len_res
          for i in range(0,len_res):
            status_err[i]=status_err[i]+int(res[1][i])
        else:  outFile.write(line)
      inFile.close()
    outFile.write(" ".join(str(x) for x in status_ok)+" tests passed, "+" ".join(str(x) for x in status_err)+" failed\n")
    outFile.close()
    save = True
    if os.path.exists(runall):
      e, o = run_cmd("diff %s.tmp %s | wc -l" % (runall, runall))
      if o=="0": save=False
    if save: run_cmd("mv %s.tmp %s" % (runall, runall))
    return

  def update_known_errors(self):
    known_errors = {}
    for logFile in glob.glob(self.basedir+'/*/known_error.json'):
      try:
        wf = logFile.split("/")[-2].split("_")[0]
        known_errors[wf] = json.load(open(logFile))
      except Exception as e:
        print("ERROR:",e) 
    outFile = open(os.path.join(self.outdir,"all_known_errors.json"),"w")
    json.dump(known_errors, outFile)
    outFile.close()

  def update_wftime(self):
    time_info = {}
    for logFile in glob.glob(self.basedir+'/*/time.log'):
      try:
        wf = logFile.split("/")[-2].split("_")[0]
        inFile = open(logFile)
        line  = inFile.readline().strip()
        inFile.close()
        m = re.match("^(\d+)(\.\d+|)$",line)
        if m: time_info[wf]=int(m.group(1))
      except Exception as e:
        print("ERROR:",e) 
    outFile = open(os.path.join(self.outdir,"relval-times.json"),"w")
    json.dump(time_info, outFile)
    outFile.close()

  def parseLog(self):
    logData = {}
    logRE = re.compile('^.*/([1-9][0-9]*(\.[0-9]+|))_[^/]+/step([1-9])_.*\.log$')
    max_steps = 0
    for logFile in glob.glob(self.basedir+'/[1-9]*/step[0-9]*.log'):
      m = logRE.match(logFile)
      if not m: continue
      wf = m.group(1)
      step = int(m.group(3))
      if step>max_steps: max_steps=step
      if wf not in logData:
        logData[wf] = {'steps': {}, 'events' : [], 'failed' : [], 'warning' : []}
      if step not in logData[wf]['steps']:
        logData[wf]['steps'][step]=logFile
    cache_read=0
    log_processed=0
    for wf in logData:
      for k in logData[wf]:
        if k == 'steps': continue
        for s in range(0, max_steps):
          logData[wf][k].append(-1)
      index =0
      for step in sorted(logData[wf]['steps']):
        data = [0, 0, 0]
        logFile = logData[wf]['steps'][step]
        json_cache = os.path.dirname(logFile)+"/logcache_"+str(step)+".json"
        log_reader_config_path = logFile + "-read_config"
        config_list = []
        cache_ok = False
        if (os.path.exists(json_cache)) and (os.path.getmtime(logFile)<=os.path.getmtime(json_cache)):
          try:
            jfile = open(json_cache,"r")
            data = json.load(jfile)
            jfile.close()
            cache_read+=1
            cache_ok = True
          except:
            os.remove(json_cache)
        if not cache_ok:
          try:
            es_parse_log(logFile)
          except Exception as e:
            print("Sending log information to elasticsearch failed" , str(e))
          inFile = open(logFile)
          for line_nr, line in enumerate(inFile):
            config_list = add_exception_to_config(line, line_nr, config_list)
            if '%MSG-w' in line: data[1]=data[1]+1
            if '%MSG-e' in line: data[2]=data[2]+1
            if 'Begin processing the ' in line: data[0]=data[0]+1
          inFile.close()
          jfile = open(json_cache,"w")
          json.dump(data,jfile)
          jfile.close()
          transform_and_write_config_file(log_reader_config_path, config_list)
          log_processed+=1
        logData[wf]['events'][index] = data[0]
        logData[wf]['failed'][index] = data[2]
        logData[wf]['warning'][index] = data[1]
        index+=1
      del logData[wf]['steps']

    print("Log processed: ",log_processed)
    print("Caches read:",cache_read)
    from pickle import Pickler
    outFile = open(os.path.join(self.outdir,'runTheMatrixMsgs.pkl'), 'wb')
    pklFile = Pickler(outFile, protocol=2)
    pklFile.dump(logData)
    outFile.close()
    return

