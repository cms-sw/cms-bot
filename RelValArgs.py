#!/usr/bin/env python
from __future__ import print_function
import re
from os import environ
from os.path import dirname, abspath
monitor_script = ""
try:
  import psutil
  monitor_script = dirname(abspath(__file__))+"/monitor_workflow.py"
except:
 print("Monitering of relval steps disabled: import psutils failed")

RELVAL_KEYS = {"customiseWithTimeMemorySummary":[],
               "enableIMT":[],
               "PREFIX":[],
               "JOB_REPORT":[],
               "USE_INPUT":[],
               "THREADED":[],
               "SLHC_WORKFLOWS":[],
               "TIMEOUT": []
              }
THREADED_ROOT="NON_THREADED_CMSSW"
THREADED_IBS="NON_THREADED_CMSSW"
if not 'CMSSW_NON_THREADED' in environ:
  THREADED_ROOT="CMSSW_9_[1-9]_ROOT6_X_.+"
  THREADED_IBS="CMSSW_(8_[1-9][0-9]*|(9|[1-9][0-9]+)_[0-9]+)_.+:slc[6-9]_amd64_gcc(5[3-9]|[6-9])[0-9]+"
RELVAL_KEYS["customiseWithTimeMemorySummary"].append([".+" ,"--customise Validation/Performance/TimeMemorySummary.customiseWithTimeMemorySummary"])
RELVAL_KEYS["PREFIX"].append(["CMSSW_[1-7]_.+"             ,"--prefix '%s timeout --signal SIGSEGV @TIMEOUT@ '" % monitor_script])
RELVAL_KEYS["PREFIX"].append(["CMSSW_.+"                   ,"--prefix '%s timeout --signal SIGTERM @TIMEOUT@ '" % monitor_script])
RELVAL_KEYS["JOB_REPORT"].append([".+"                     ,"--job-reports"])
RELVAL_KEYS["USE_INPUT"].append([".+"                      ,"--useInput all"])
RELVAL_KEYS["THREADED"].append([THREADED_IBS               ,"-t 4"])
RELVAL_KEYS["SLHC_WORKFLOWS"].append(["_SLHCDEV_"          ,"-w upgrade -l 10000,10061,10200,10261,10800,10861,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"])
RELVAL_KEYS["SLHC_WORKFLOWS"].append(["_SLHC_"             ,"-w upgrade -l 10000,10061,10200,10261,12200,12261,14400,14461,12600,12661,14000,14061,12800,12861,13000,13061,13800,13861"])
RELVAL_KEYS["enableIMT"].append([THREADED_ROOT             ,"--customise FWCore/Concurrency/enableIMT.enableIMT"])
RELVAL_KEYS["TIMEOUT"].append(["(_ASAN_|_ppc64|_aarch64_)" ,"14400"])
RELVAL_KEYS["TIMEOUT"].append([".+"                        ,"7200"])

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
    if key in RELVAL_KEYS:
      for exp,data in RELVAL_KEYS[key]:
        if re.search(exp,rel_arch):
          val = data + " "
          break
    cmd = cmd.replace(m.group(1), val)
    m=re.search("(@([a-zA-Z_]+)@)",cmd)
  
  return re.sub("\s+"," ",cmd)

def FixWFArgs(release, arch, wf, args):
  if isThreaded(release, arch):
    NonThreadedWF = ["101.0","102.0"]
    if wf in NonThreadedWF:
      for k in [ "THREADED", "enableIMT" ]:
        if (k in RELVAL_KEYS):
          thds  = [d for e,d in RELVAL_KEYS[k] if THREADED_IBS == e]
          roots = [d for e,d in RELVAL_KEYS[k] if THREADED_ROOT == e]
          if thds:
            args = args.replace(thds[0],"")
          elif roots:
            args = args.replace(roots[0],"")
  return args

