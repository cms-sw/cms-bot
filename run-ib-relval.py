#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
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
import re, socket
from time import time

SCRIPT_DIR = dirname(abspath(argv[0]))


def process_relvals(threads=None, cmssw_version=None, arch=None, cmssw_base=None, logger=None):
    pass


if __name__ == "__main__":
    parser = OptionParser(usage="%prog -i|--id <jobid> -l|--list <list of workflows>")
    parser.add_option("-i", "--id", dest="jobid", help="Job Id e.g. 1of3", default="1of1")
    parser.add_option(
        "-l",
        "--list",
        dest="workflow",
        help="List of workflows to run e.g. 1.0,2.0,3.0 or -s",
        type=str,
        default=None,
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not upload results",
        default=False,
    )
    parser.add_option(
        "-f",
        "--force",
        dest="force",
        help="Force running of workflows without checking the server for previous run",
        action="store_true",
        default=False,
    )
    parser.add_option(
        "-N",
        "--non-threaded",
        dest="nonThreaded",
        action="store_true",
        help="Do not run in threaded mode",
        default=False,
    )
    parser.add_option(
        "-J",
        "--job-config",
        dest="jobConfig",
        help="Extra arguments to pass to jobscheduler",
        type=str,
        default="",
    )
    opts, args = parser.parse_args()

    if len(args) > 0:
        parser.error("Too many/few arguments")
    if not opts.workflow:
        parser.error("Missing -l|--list <workflows> argument.")
    if (
        ("CMSSW_VERSION" not in environ)
        or ("CMSSW_BASE" not in environ)
        or ("SCRAM_ARCH" not in environ)
    ):
        print(
            "ERROR: Unable to file the release environment, please make sure you have set the cmssw environment before calling this script"
        )
        exit(1)

    if opts.dryRun:
        environ["CMSSW_DRY_RUN"] = "true"
    if opts.nonThreaded:
        environ["CMSSW_NON_THREADED"] = "true"
    elif "CMSSW_NON_THREADED" in environ:
        del os.environ["CMSSW_NON_THREADED"]
    thrds = cmsRunProcessCount
    cmssw_ver = environ["CMSSW_VERSION"]
    arch = environ["SCRAM_ARCH"]
    cmssw_base = environ["CMSSW_BASE"]
    logger = None
    if not opts.dryRun:
        logger = LogUpdater(dirIn=cmssw_base)
    if logger and not opts.force:
        doneWFs = logger.getDoneRelvals()
        print("Already done workflows: ", doneWFs)
        wfs = opts.workflow.split(",")
        opts.workflow = ",".join([w for w in wfs if (w not in doneWFs)])
        print("Workflow to run:", opts.workflow)
    else:
        print("Force running all workflows")

    if re.match("^CMSSW_(9_([3-9]|[1-9][0-9]+)|[1-9][0-9]+)_.*$", cmssw_ver):
        e = 0
        if opts.workflow:
            stime = time()
            p = Popen("%s/jobs/create-relval-jobs.py %s" % (SCRIPT_DIR, opts.workflow), shell=True)
            e = waitpid(p.pid, 0)[1]
            print("Time took to create jobs:", int(time() - stime), "sec")
            if e:
                exit(e)

            p = None
            stime = time()
            xopt = "-c 150 -m 85"
            if "lxplus" in socket.gethostname():
                xopt = "-c 120 -m 40"
            p = Popen(
                "cd %s/pyRelval ; %s/jobs/jobscheduler.py -M 0 %s -o time %s"
                % (cmssw_base, SCRIPT_DIR, xopt, opts.jobConfig),
                shell=True,
            )
            e = waitpid(p.pid, 0)[1]
            print("Time took to create jobs:", int(time() - stime), "sec")
        else:
            print("No workflow to run.")
        system("touch " + cmssw_base + "/done." + opts.jobid)
        if logger:
            logger.updateRelValMatrixPartialLogs(cmssw_base, "done." + opts.jobid)
        exit(e)

    if isThreaded(cmssw_ver, arch):
        print("Threaded IB Found")
        thrds = int(MachineMemoryGB / 4.5)
        if thrds == 0:
            thrds = 1
    elif "fc24_ppc64le_" in arch:
        print("FC22 IB Found")
        thrds = int(MachineMemoryGB / 4)
    elif "fc24_ppc64le_" in arch:
        print("CentOS 7.2 + PPC64LE Found")
        thrds = int(MachineMemoryGB / 3)
    else:
        print("Normal IB Found")
    if thrds > cmsRunProcessCount:
        thrds = cmsRunProcessCount
    known_errs = get_known_errors(cmssw_ver, arch, "relvals")
    matrix = PyRelValsThread(thrds, cmssw_base + "/pyRelval", opts.jobid)
    matrix.setArgs(GetMatrixOptions(cmssw_ver, arch))
    matrix.run_workflows(opts.workflow.split(","), logger, known_errors=known_errs)
