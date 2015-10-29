from commands import getstatusoutput
from os import getcwd
from time import asctime, time, strftime, gmtime
import sys, re
from sys import platform

def getHostDomain():
    site = ''
    import socket
    site = socket.getfqdn()
    fqdn = site.split('.')
    return fqdn[0], fqdn[-2]+'.'+fqdn[-1]

def getDomain():
    return getHostDomain()[1]

def getHostName():
    return getHostDomain()[0]

def _getCPUCount():
    cmd = ""
    if platform == "darwin":
      cmd = "sysctl -n hw.ncpu"
    elif platform.startswith("linux"):
      cmd = "cat /proc/cpuinfo | grep '^processor' | wc -l"
    error, count = getstatusoutput(cmd)
    if error:
      print "Warning: unable to detect cpu count. Using 4 as default value"
      out = "4"
    if not count.isdigit():
      return 4
    return int(count)

def _memorySizeGB():
    cmd = ""
    if platform == "darwin":
      cmd = "sysctl -n hw.memsize"
    elif platform.startswith("linux"):
      cmd = "free -t -m | grep '^Mem: *' | awk '{print $2}'"
    error, out = getstatusoutput(cmd)
    if error:
      print "Warning: unable to detect memory info. Using 8GB as default value"
      return 8
    if not out.isdigit():
      return 8
    from math import ceil
    count = int(ceil(float(out)/1024))
    if count == 0: count =1
    return count

MachineMemoryGB = _memorySizeGB()
MachineCPUCount = _getCPUCount()

def _compilationProcesses():
    count = MachineCPUCount * 2
    if MachineMemoryGB<count: count = MachineMemoryGB
    return count

def _cmsRunProcesses():
    count = int(MachineMemoryGB/2)
    if count==0: count =1
    if MachineCPUCount<count: count = MachineCPUCount
    return count

compilationPrcoessCount = _compilationProcesses()
cmsRunProcessCount = _cmsRunProcesses()
if "lxplus" in getHostName():
  cmsRunProcessCount = int(cmsRunProcessCount/2)+1
  MachineCPUCount = int (MachineCPUCount/2)+1

def doCmd(cmd, dryRun=False, inDir=None):
  if not inDir:
    print "--> "+asctime()+ " in ", getcwd() ," executing ", cmd
  else:
    print "--> "+asctime()+ " in " + inDir + " executing ", cmd
    cmd = "cd " + inDir + "; "+cmd
  sys.stdout.flush()
  sys.stderr.flush()
  start = time()
  ret = 0
  outX = ""
  while cmd.endswith(";"): cmd=cmd[:-1]
  if dryRun:
    print "DryRun for: "+cmd
  else:
    ret, outX = getstatusoutput(cmd)
    print outX
  stop = time()
  print "--> "+asctime()+" cmd took", stop-start, "sec. ("+strftime("%H:%M:%S",gmtime(stop-start))+")"
  sys.stdout.flush()
  sys.stderr.flush()
  return (ret,outX)

def getIBReleaseInfo(rel):
  m = re.match("^CMSSW_(\d+_\d+(_[A-Z0-9]+|))_X(_[A-Z]+|)_(\d\d\d\d-\d\d-\d\d-(\d\d)\d\d)",rel)
  if not m: return ("","","")
  rc = m.group(1).replace("_",".")
  from datetime import datetime
  day = datetime.strptime(m.group(4),"%Y-%m-%d-%H%M").strftime("%a").lower()
  hour = m.group(5)
  return (rc, day, hour)

