#!/bin/env python3
from __future__ import print_function

from hashlib import sha1
import os, json, datetime, sys, copy, re
from glob import glob
from os.path import exists, dirname, getmtime
from es_utils import send_payload
from _py2with3compatibility import run_cmd
from cmsutils import cmsswIB2Week
from logreaderUtils import transform_and_write_config_file, add_exception_to_config, ResultTypeEnum
import traceback


def sha1hexdigest(data):
    return sha1(data.encode()).hexdigest()


def send_unittest_dataset(datasets, payload, id, index, doc):
    for ds in datasets:
        print("Processing ", ds)
        if not "root://" in ds:
            continue
        ds_items = ds.split("?", 1)
        ds_items.append("")
        ibeos = "/store/user/cmsbuild"
        if ibeos in ds_items[0]:
            ds_items[0] = ds_items[0].replace(ibeos, "")
        else:
            ibeos = ""
        payload["protocol"] = ds_items[0].split("/store/", 1)[0] + ibeos
        payload["protocol_opts"] = ds_items[1]
        payload["lfn"] = "/store/" + ds_items[0].split("/store/", 1)[1].strip()
        print("Sending", index, doc, sha1hexdigest(id + ds), json.dumps(payload))
        send_payload(index, doc, sha1hexdigest(id + ds), json.dumps(payload))


def process_unittest_log(logFile):
    t = getmtime(logFile)
    timestp = int(t * 1000)
    pathInfo = logFile.split("/")
    architecture = pathInfo[4]
    release = pathInfo[8]
    week, rel_sec = cmsswIB2Week(release)
    package = pathInfo[-3] + "/" + pathInfo[-2]
    payload_dataset = {"type": "unittest"}
    payload_dataset["release"] = release
    release_queue = "_".join(release.split("_", -1)[:-1]).split("_", 3)
    payload_dataset["release_queue"] = "_".join(release_queue[0:3])
    flavor = release_queue[-1]
    if flavor == "X":
        flavor = "DEFAULT"
    payload_dataset["flavor"] = flavor
    payload_dataset["architecture"] = architecture
    payload_dataset["@timestamp"] = timestp

    payload_utest = copy.deepcopy(payload_dataset)
    del payload_utest["type"]

    inStacktrace = False
    stacktrace = []
    datasets = []

    config_list = []
    custom_rule_set = [
        {
            "str_to_match": "test (.*) had ERRORS",
            "name": "{0} failed",
            "control_type": ResultTypeEnum.ISSUE,
        },
        {
            "str_to_match": r'===== Test "([^\s]+)" ====',
            "name": "{0}",
            "control_type": ResultTypeEnum.TEST,
        },
    ]

    pkgTestStartRe = re.compile('^===== Test "(.*)" ====')
    pkgTestEndRe = re.compile(r"^\^\^\^\^ End Test (.*) \^\^\^\^")
    pkgTestResultRe = re.compile(".*---> test ([^ ]+) (had ERRORS|succeeded)")

    with open(logFile, encoding="ascii", errors="ignore") as f:
        utname = None
        datasets = []
        test_status = -1
        for index, l in enumerate(f):
            l = l.strip()
            config_list = add_exception_to_config(l, index, config_list, custom_rule_set)
            if m := pkgTestStartRe.match(l):
                utname = m[1]
                test_status = -1
                datasets = []
                continue

            if m := pkgTestResultRe.match(l):
                if m[1] != utname:
                    print(
                        "ERROR: Unit test name mismatch - expected {0}, got {1}".format(
                            utname, m[1]
                        )
                    )  # TODO: do we want a more visible error (exit 1)? Or maybe skip this file?
                else:
                    test_status = 0 if m[2] == "succeeded" else 1
                continue

            if m := pkgTestEndRe.match(l):
                if m[1] != utname:
                    print(
                        "ERROR: Unit test name mismatch - expected {0}, got {1}".format(
                            utname, m[1]
                        )
                    )  # TODO: do we want a more visible error (exit 1)? Or maybe skip this file?
                    continue

                if test_status == -1:
                    print("ERROR: test state for UT {0} unknown".format(utname))
                    continue

                payload_utest["url"] = (
                    "https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/"
                    + architecture
                    + "/"
                    + release
                    + "/unitTestLogs/"
                    + package
                )
                payload_utest["status"] = test_status
                payload_utest["name"] = utname
                payload_utest["package"] = package
                if stacktrace:
                    payload_utest["stacktrace"] = "\n".join(stacktrace)
                    stacktrace = []
                utest_id = sha1hexdigest(release + architecture + utname)
                print("==> ", json.dumps(payload_dataset) + "\n")
                send_payload(index, "unittests", utest_id, json.dumps(payload_utest))

                payload_dataset["name"] = "%s/%s" % (package, utname)
                dataset_id = sha1hexdigest(release + architecture + package + utname)
                print("==> ", json.dumps(payload_dataset) + "\n")
                send_unittest_dataset(
                    datasets, payload_dataset, dataset_id, "ib-dataset-" + week, "unittest-dataset"
                )
                continue

            if " Initiating request to open file " in l:
                try:
                    rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
                    if (not "file:" in rootfile) and (not rootfile in datasets):
                        datasets.append(rootfile)
                except Exception as e:
                    print("ERROR: ", logFile, e)
                    traceback.print_exc(file=sys.stdout)
                continue

            if "sig_dostack_then_abort" in l:
                inStacktrace = True
                continue

            if inStacktrace and not l.startswith("#"):
                inStacktrace = False
                continue

            if inStacktrace:
                if len(stacktrace) < 20:
                    stacktrace.append(l)
                continue

    transform_and_write_config_file(logFile + "-read_config", config_list)
    return


def process_addon_log(logFile):
    t = getmtime(logFile)
    timestp = int(t * 1000)
    pathInfo = logFile.split("/")
    architecture = pathInfo[4]
    release = pathInfo[8]
    week, rel_sec = cmsswIB2Week(release)
    datasets = []
    payload = {"type": "addon"}
    payload["release"] = release
    payload["architecture"] = architecture
    payload["@timestamp"] = timestp
    payload["name"] = pathInfo[-1].split("-")[1].split("_cmsRun_")[0].split("_cmsDriver.py_")[0]
    id = sha1hexdigest(release + architecture + "addon" + payload["name"])
    config_list = []
    with open(logFile, encoding="ascii", errors="ignore") as f:
        for index, l in enumerate(f):
            l = l.strip()
            config_list = add_exception_to_config(l, index, config_list)
            if " Initiating request to open file " in l:
                try:
                    rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
                    if (not "file:" in rootfile) and (not rootfile in datasets):
                        datasets.append(rootfile)
                except:
                    pass
    send_unittest_dataset(datasets, payload, id, "ib-dataset-" + week, "addon-dataset")
    transform_and_write_config_file(logFile + "-read_config", config_list)
    return


def process_hlt_log(logFile):
    t = getmtime(logFile)
    timestp = int(t * 1000)
    pathInfo = logFile.split("/")
    architecture = pathInfo[-2]
    release = pathInfo[-3]
    week, rel_sec = cmsswIB2Week(release)
    datasets = []
    payload = {"type": "hlt"}
    payload["release"] = release
    payload["architecture"] = architecture
    payload["@timestamp"] = timestp
    payload["name"] = pathInfo[-1][:-4]
    id = sha1hexdigest(release + architecture + "hlt" + payload["name"])
    with open(logFile, encoding="ascii", errors="ignore") as f:
        for index, l in enumerate(f):
            l = l.strip()
            if " Initiating request to open file " in l:
                try:
                    rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
                    if (not "file:" in rootfile) and (not rootfile in datasets):
                        datasets.append(rootfile)
                except:
                    pass
    send_unittest_dataset(datasets, payload, id, "ib-dataset-" + week, "hlt-dataset")
    return


logs = run_cmd("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'unitTestLogs.zip'")
logs = logs[1].split("\n")
# process zip log files
for logFile in logs:
    flagFile = logFile + ".checked"
    if not exists(flagFile):
        utdir = dirname(logFile)
        print("Working on ", logFile)
        try:
            err, utlogs = run_cmd(
                "cd %s; rm -rf UT; mkdir UT; cd UT; unzip ../unitTestLogs.zip" % utdir
            )
            err, utlogs = run_cmd("find %s/UT -name 'unitTest.log' -type f" % utdir)
            if not err:
                for utlog in utlogs.split("\n"):
                    process_unittest_log(utlog)
                run_cmd("touch %s" % flagFile)
        except Exception as e:
            print("ERROR: ", logFile, e)
            traceback.print_exc(file=sys.stdout)
        run_cmd("cd %s/UT ; zip -r ../unitTestLogs.zip ." % utdir)
        run_cmd("rm -rf %s/UT" % utdir)

logs = run_cmd("find /data/sdt/buildlogs -mindepth 6 -maxdepth 6 -name 'addOnTests.zip'")
logs = logs[1].split("\n")
# process zip log files
for logFile in logs:
    flagFile = logFile + ".checked"
    if not exists(flagFile):
        utdir = dirname(logFile)
        print("Working on ", logFile)
        try:
            err, utlogs = run_cmd(
                "cd %s; rm -rf AO; mkdir AO; cd AO; unzip ../addOnTests.zip" % utdir
            )
            err, utlogs = run_cmd("find %s/AO -name '*.log' -type f" % utdir)
            if not err:
                for utlog in utlogs.split("\n"):
                    process_addon_log(utlog)
                run_cmd("touch %s" % flagFile)
        except Exception as e:
            print("ERROR:", e)
        run_cmd("cd %s/AO ; zip -r ../addOnTests.zip ." % utdir)
        run_cmd("rm -rf %s/AO" % utdir)

dirs = run_cmd(
    "find /data/sdt/SDT/jenkins-artifacts/HLT-Validation -maxdepth 2 -mindepth 2 -type d"
)[1].split("\n")
for d in dirs:
    flagFile = d + ".checked"
    if exists(flagFile):
        continue
    for logFile in glob(d + "/*.log"):
        print("Working on ", logFile)
        try:
            process_hlt_log(logFile)
        except Exception as e:
            print("ERROR:", e)
    run_cmd("touch %s" % flagFile)
