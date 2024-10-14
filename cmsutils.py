from __future__ import print_function
from _py2with3compatibility import run_cmd
from os import getcwd
from time import asctime, time, strftime, gmtime
import sys, re
from sys import platform
from os.path import dirname, abspath

try:
    CMS_BOT_DIR = dirname(abspath(__file__))
except Exception as e:
    from sys import argv

    CMS_BOT_DIR = dirname(abspath(argv[0]))


def getHostDomain():
    site = ""
    import socket

    site = socket.getfqdn()
    fqdn = site.split(".")
    hname = fqdn[0]
    dname = "cern.ch"
    if len(fqdn) > 2:
        dname = fqdn[-2] + "." + fqdn[-1]
    return hname, dname


def getDomain():
    return getHostDomain()[1]


def getHostName():
    return getHostDomain()[0]


def _getCPUCount():
    cmd = "nproc"
    if platform == "darwin":
        cmd = "sysctl -n hw.ncpu"
    error, count = run_cmd(cmd)
    if error:
        print("Warning: unable to detect cpu count. Using 4 as default value")
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
    error, out = run_cmd(cmd)
    if error:
        print("Warning: unable to detect memory info. Using 8GB as default value")
        return 8
    if not out.isdigit():
        return 8
    from math import ceil

    count = int(ceil(float(out) / 1024))
    if count == 0:
        count = 1
    return count


MachineMemoryGB = _memorySizeGB()
MachineCPUCount = _getCPUCount()


def _compilationProcesses():
    count = MachineCPUCount * 2
    if MachineMemoryGB < count:
        count = MachineMemoryGB
    return count


def _cmsRunProcesses():
    count = int((MachineMemoryGB + 1) / 2)
    if count == 0:
        count = 1
    if MachineCPUCount < count:
        count = MachineCPUCount
    return count


compilationPrcoessCount = _compilationProcesses()
cmsRunProcessCount = _cmsRunProcesses()


def doCmd(cmd, dryRun=False, inDir=None, debug=True):
    if not inDir:
        if debug:
            print("--> " + asctime() + " in ", getcwd(), " executing ", cmd)
    else:
        if debug:
            print("--> " + asctime() + " in " + inDir + " executing ", cmd)
        cmd = "cd " + inDir + "; " + cmd
    sys.stdout.flush()
    sys.stderr.flush()
    start = time()
    ret = 0
    outX = ""
    while cmd.endswith(";"):
        cmd = cmd[:-1]
    if dryRun:
        print("DryRun for: " + cmd)
    else:
        ret, outX = run_cmd(cmd)
        if debug:
            print(outX)
    stop = time()
    if debug:
        print(
            "--> " + asctime() + " cmd took",
            stop - start,
            "sec. (" + strftime("%H:%M:%S", gmtime(stop - start)) + ")",
        )
    sys.stdout.flush()
    sys.stderr.flush()
    return (ret, outX)


def getIBReleaseInfo(rel):
    m = re.match(
        "^CMSSW_(\\d+_\\d+(_[A-Z][A-Za-z0-9]+|))_X(_[A-Z]+|)_(\\d\\d\\d\\d-\\d\\d-\\d\\d-(\\d\\d)\\d\\d)",
        rel,
    )
    if not m:
        return ("", "", "")
    rc = m.group(1).replace("_", ".")
    from datetime import datetime

    day = datetime.strptime(m.group(4), "%Y-%m-%d-%H%M").strftime("%a").lower()
    hour = m.group(5)
    return (rc, day, hour)


def epoch2week(epoch_sec, week_offset=4):
    week = int(((epoch_sec / 86400) + 4) / 7)
    if week_offset > 1:
        week = week - (week % week_offset)
    return str(week)


def cmsswIB2Week(release, week_offset=4):
    from datetime import datetime
    rel_date = "-".join(release.split("_")[-1].split("-")[:-1])+"-1200"
    rel_sec = int(datetime.strptime(rel_date, "%Y-%m-%d-%H%M").strftime("%s"))
    return (epoch2week(rel_sec, week_offset), rel_sec)


#
# Reads config.map and returns a list of the architectures for which a release needs to be built.
# If the list is empty it means that it didn't find any architecture for that release queue, or
# that the IBs are disabled.
#
def get_config_map_properties(filters=None):
    CONFIG_MAP_FILE = CMS_BOT_DIR + "/config.map"
    specs = []
    f = open(CONFIG_MAP_FILE, "r")
    lines = [l.strip(" \n\t;") for l in f.read().split("\n") if l.strip(" \n\t;")]
    for line in lines:
        entry = dict(x.split("=", 1) for x in line.split(";") if x)
        skip = False
        if filters:
            for k in filters:
                if (k in entry) and (entry[k] == filters[k]):
                    skip = True
                    break
        if not skip:
            specs.append(entry)
    return specs


def percentile(percentage, data, dlen):
    R = (dlen + 1) * percentage / 100.0
    IR = int(R)
    if IR >= dlen:
        return data[-1]
    elif IR == 0:
        return data[0]
    FR = int((R - IR) * 100)
    res = data[IR - 1]
    if FR > 0:
        res = (FR / 100.0) * (data[IR] - res) + res
    return res


def get_full_release_archs(release_name):
    data = {}
    ret, out = run_cmd("grep 'label=" + release_name + ";' " + CMS_BOT_DIR + "/releases.map")
    for line in out.split("\n"):
        arch = ""
        prod = 0
        for item in [x.split("=") for x in line.split(";")]:
            if item[0] == "architecture":
                arch = item[1]
            elif item[0] == "prodarch":
                prod = item[1]
        if arch:
            data[arch] = prod
    return data
