#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
import sys, json, glob, os, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
CMS_BOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, CMS_BOT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from cmssw_known_errors import get_known_errors
from logUpdater import LogUpdater
from _py2with3compatibility import run_cmd


def update_cmdlog(workflow_dir, jobs):
    if not jobs["commands"]:
        return
    workflow_cmdlog = os.path.join(workflow_dir, "cmdLog")
    if not os.path.exists(workflow_cmdlog):
        return
    wfile = open(workflow_cmdlog, "a")
    for job in jobs["commands"]:
        if job["exit_code"] >= 0:
            wfile.write("\n# in: /some/build/directory going to execute ")
            for cmd in job["command"].split(";"):
                if cmd:
                    wfile.write(cmd + "\n")
    wfile.close()
    return


def fix_lognames(workflow_dir):
    workflow_id = os.path.basename(workflow_dir).split("_", 1)[1]
    for log in glob.glob(os.path.join(workflow_dir, "step*_*.log")):
        logname = os.path.basename(log)
        step = logname.split("_", 1)[0]
        deslog = step + ".log"
        if logname.endswith("_dasquery.log"):
            deslog = "%s_%s.log" % (step, workflow_id)
        run_cmd("ln -s %s %s/%s" % (logname, workflow_dir, deslog))


def update_worklog(workflow_dir, jobs):
    if not jobs["commands"]:
        return False
    workflow_logfile = os.path.join(workflow_dir, "workflow.log")
    if not os.path.exists(workflow_logfile):
        return False
    workflow_time = 0
    exit_codes = ""
    test_passed = ""
    test_failed = ""
    steps_res = []
    failed = False
    step_num = 0
    for job in jobs["commands"]:
        step_num += 1
        try:
            m = re.match("^.*\s+step([1-9][0-9]*)\s+.*$", job["command"])
            if m:
                cmd_step = int(m.group(1))
            else:
                m = re.match(".*\s*>\s*step([1-9][0-9]*)_[^\s]+\.log.*$", job["command"])
                if m:
                    cmd_step = int(m.group(1))
                else:
                    cmd_step = int(job["command"].split(" step", 1)[-1].strip().split(" ")[0])
            while cmd_step > step_num:
                das_log = os.path.join(workflow_dir, "step%s_dasquery.log" % step_num)
                step_num += 1
                if os.path.exists(das_log):
                    e, o = run_cmd("grep ' tests passed,' %s" % workflow_logfile)
                    if o == "":
                        return False
                    ecodes = o.split()
                    if ecodes[step_num - 2] == "0":
                        exit_codes += " 1"
                        test_passed += " 0"
                        test_failed += " 1"
                        failed = True
                        steps_res.append("FAILED")
                        continue
                exit_codes += " 0"
                test_passed += " 1"
                test_failed += " 0"
                steps_res.append("PASSED")
        except Exception as e:
            print("ERROR: Unable to find step number:", job["command"])
            pass
        if job["exit_code"] == -1:
            failed = True
        if job["exit_code"] > 0:
            exit_codes += " " + str(job["exit_code"])
            test_passed += " 0"
            test_failed += " 1"
            failed = True
            steps_res.append("FAILED")
        else:
            exit_codes += " 0"
            test_failed += " 0"
            if failed:
                test_passed += " 0"
            else:
                test_passed += " 1"
            steps_res.append("NORUN" if failed else "PASSED")
    step_str = ""
    for step, res in enumerate(steps_res):
        step_str = "%s Step%s-%s" % (step_str, step, res)
    e, o = run_cmd(
        "grep ' exit: ' %s | sed 's|exit:.*$|exit: %s|'" % (workflow_logfile, exit_codes.strip())
    )
    o = re.sub("\s+Step0-.+\s+-\s+time\s+", step_str + "  - time ", o)
    wfile = open(workflow_logfile, "w")
    wfile.write(o + "\n")
    wfile.write("%s tests passed, %s failed\n" % (test_passed.strip(), test_failed.strip()))
    wfile.close()
    return True


def update_timelog(workflow_dir, jobs):
    workflow_time = os.path.join(workflow_dir, "time.log")
    wf_time = 5
    for job in jobs["commands"]:
        if job["state"] == "Done":
            wf_time += job["exec_time"]
    wfile = open(workflow_time, "w")
    wfile.write("%s\n" % wf_time)
    wfile.close()


def update_hostname(workflow_dir):
    run_cmd("hostname > %s/hostname" % workflow_dir)


def update_known_error(worflow, workflow_dir):
    known_errors = get_known_errors(
        os.environ["CMSSW_VERSION"], os.environ["SCRAM_ARCH"], "relvals"
    )
    if worflow in known_errors:
        json.dump(known_errors[workflow], open("%s/known_error.json" % workflow_dir, "w"))
    return


def upload_logs(workflow, workflow_dir, exit_code):
    files_to_keep = [".txt", ".xml", ".log", ".py", ".json", "/cmdLog", "/hostname", ".done"]
    basedir = os.path.dirname(workflow_dir)
    for wf_file in glob.glob("%s/*" % workflow_dir):
        found = False
        for ext in files_to_keep:
            if wf_file.endswith(ext):
                found = True
                break
        if not found:
            print("Removing ", wf_file)
            run_cmd("rm -rf %s" % wf_file)
    logger = LogUpdater(dirIn=os.environ["CMSSW_BASE"])
    logger.updateRelValMatrixPartialLogs(basedir, os.path.basename(workflow_dir))


if __name__ == "__main__":
    jobs = json.load(open(sys.argv[1]))
    exit_code = 0
    for cmd in jobs["commands"]:
        if cmd["exit_code"] > 0:
            exit_code = cmd["exit_code"]
            break
    workflow = jobs["name"]
    workflow_dir = os.path.abspath(glob.glob("%s_*" % workflow)[0])
    run_cmd("mv %s %s/job.json" % (sys.argv[1], workflow_dir))
    fix_lognames(workflow_dir)
    if update_worklog(workflow_dir, jobs):
        update_cmdlog(workflow_dir, jobs)
    update_timelog(workflow_dir, jobs)
    update_hostname(workflow_dir)
    update_known_error(workflow, workflow_dir)
    if not "CMSSW_DRY_RUN" in os.environ:
        upload_logs(workflow, workflow_dir, exit_code)
    run_cmd("touch %s/workflow_upload_done" % workflow_dir)
