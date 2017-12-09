#!/usr/bin/env python
import re
from os.path import dirname, abspath
monitor_script = ""
try:
  import psutil
  monitor_script = dirname(abspath(__file__))+"/monitor_workflow.py"
except:
 print "Monitering of relval steps disabled: import psutils failed"

RELVAL_KEYS = {"customiseWithTimeMemorySummary":{},
               "enableIMT":{},
               "PREFIX":{},
               "JOB_REPORT":{},
               "USE_INPUT":{},
               "THREADED":{},
               "SLHC_WORKFLOWS":{},
              }
THREADED_ROOT="CMSSW_9_[1-9]_ROOT6_X_.+"
THREADED_IBS="CMSSW_(8_[1-9][0-9]*|(9|[1-9][0-9]+)_[0-9]+)_X_.+:slc[6-9]_amd64_gcc(5[3-9]|[6-9])[0-9]+|_THREADED_X|_DEVEL_X|_ROOT6_X|_ROOT612_X"
RELVAL_KEYS["customiseWithTimeMemorySummary"][".+"] = "--customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary"
RELVAL_KEYS["PREFIX"]["CMSSW_([89]|[1-9][0-9]+)_.+"] = "--prefix '%s timeout --signal SIGTERM 7200 '" % monitor_script
RELVAL_KEYS["PREFIX"]["CMSSW_[1-7]_.+"]              = "--prefix '%s timeout --signal SIGSEGV 7200 '" % monitor_script
RELVAL_KEYS["JOB_REPORT"][".+"]             = "--job-reports"
RELVAL_KEYS["USE_INPUT"][".+"]              = "--useInput all"
RELVAL_KEYS["THREADED"][THREADED_IBS]       = "-t 4"
RELVAL_KEYS["SLHC_WORKFLOWS"]["_SLHCDEV_"]  = "-w upgrade -l 10000,10061,10200,10261,10800,10861,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
RELVAL_KEYS["SLHC_WORKFLOWS"]["_SLHC_"]     = "-w upgrade -l 10000,10061,10200,10261,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"
RELVAL_KEYS["enableIMT"][THREADED_ROOT]     = "--customise FWCore/Concurrency/enableIMT.enableIMT"

RELVAL_ARGS = []
RELVAL_ARGS.append({})
#For SLHC releases
RELVAL_ARGS[len(RELVAL_ARGS)-1]["_SLHC(DEV|)_"]="""
  @USE_INPUT@
  @SLHC_WORKFLOWS@
"""
RELVAL_ARGS[len(RELVAL_ARGS)-1]["CMSSW_4_2_"]=""

RELVAL_ARGS.append({})
#For rleease cycles >= 7
RELVAL_ARGS[len(RELVAL_ARGS)-1]["CMSSW_([1-9][0-9]|[7-9])_"]="""
  @USE_INPUT@
  @JOB_REPORT@
  --command "
    @customiseWithTimeMemorySummary@
    @enableIMT@
    @PREFIX@
  "
  @THREADED@
"""

RELVAL_ARGS.append({})
#For all other releases
RELVAL_ARGS[len(RELVAL_ARGS)-1][".+"]="""
  @USE_INPUT@
"""

def isThreaded(release, arch):
  if re.search(THREADED_IBS,release+":"+arch): return True
  return False

def GetMatrixOptions(release, arch, dasfile=None):
  rel_arch = release+":"+arch
  cmd = ""
  for rel in RELVAL_ARGS:
    for exp in rel:
      if re.search(exp,rel_arch):
        cmd = rel[exp].replace("\n"," ")
        break
    if cmd: break
  m=re.search("(@([a-zA-Z_]+)@)",cmd)
  while m:
    key = m.group(2)
    val = ""
    if RELVAL_KEYS.has_key(key):
      for exp in RELVAL_KEYS[key]:
        if re.search(exp,rel_arch): val = val + RELVAL_KEYS[key][exp] + " "
    cmd = cmd.replace(m.group(1), val)
    m=re.search("(@([a-zA-Z_]+)@)",cmd)
  
  return re.sub("\s+"," ",cmd)

def FixWFArgs(release, arch, wf, args):
  if isThreaded(release, arch):
    NonThreadedWF = ["101.0","102.0"]
    if wf in NonThreadedWF:
      for k in [ "THREADED", "enableIMT" ]:
        if (k in RELVAL_KEYS):
          if (THREADED_IBS in RELVAL_KEYS[k]):
            args = args.replace(RELVAL_KEYS[k][THREADED_IBS],"")
          elif (THREADED_ROOT in RELVAL_KEYS[k]):
            args = args.replace(RELVAL_KEYS[k][THREADED_ROOT],"")
  return args

