#!/usr/bin/env python3
from hashlib import sha1
import os, sys, json, re
from os.path import exists
from es_utils import send_payload
import xml.etree.ElementTree as ET
from cmsutils import cmsswIB2Week


def find_step_cmd(cmdfile, step):
    try:
        cmd = ""
        data = open(cmdfile, "r")
        get = iter(data)
        line = next(get)
        while line:
            if step == "step1" and "das_client" in line:
                while "step1_dasquery.log" not in line:
                    cmd = cmd + line
                    line = next(get)
                return (cmd + line).strip()
            elif "file:" + step in line:
                return line.strip()
            line = next(get)
    except:
        return None


def get_exit_code(workflow_log, step):
    try:
        d = open(workflow_log, "r")
        for line in d:
            if "exit:" in line:
                codes = list(map(int, line.split("exit:")[-1].strip().split()))
                return int(codes[step - 1])
    except:
        pass
    return -1


def es_parse_jobreport(payload, logFile):
    xmlFile = (
        "/".join(logFile.split("/")[:-1])
        + "/JobReport"
        + logFile.split("/")[-1].split("_")[0][-1]
        + ".xml"
    )
    if not os.path.exists(xmlFile):
        if not "/JobReport1.xml" in xmlFile:
            print("No JR File:", xmlFile)
        return payload
    payload["jobreport"] = "/".join(payload["url"].split("/")[:-1]) + "/" + xmlFile.split("/")[-1]
    tree = ET.parse(xmlFile)
    root = tree.getroot()
    events_read = []
    total_events = []
    for i in root.iter("EventsRead"):
        events_read.append(i.text)
    for i in root.iter("TotalEvents"):
        total_events.append(i.text)
    if events_read:
        payload["events_read"] = max(events_read)
    if total_events:
        payload["total_events"] = max(total_events)
    reports_p = root.iter("PerformanceReport")
    for i in reports_p:
        summaries = i.iter("PerformanceSummary")
        for j in summaries:
            if j.get("Metric") == "SystemMemory" or j.get("Metric") == "StorageStatistics":
                continue
            if j.get("Metric") == "ApplicationMemory":
                metrics_list = j.iter()
                for i in metrics_list:
                    name = i.get("Name")
                    val = i.get("Value")
                    if (not val) or ("nan" in val):
                        val = ""
                    payload[name] = val
            elif j.get("Metric") == "Timing":
                metrics_list = j.iter()
                for i in metrics_list:
                    val = i.get("Value")
                    if (not val) or ("nan" in val):
                        val = ""
                    elif "e" in val:
                        val = float(val)
                    payload[i.get("Name")] = val
    return payload


def es_parse_log(logFile):
    t = os.path.getmtime(logFile)
    timestp = int(t * 1000)
    payload = {}
    pathInfo = logFile.split("/")
    architecture = pathInfo[4]
    release = pathInfo[8]
    workflow = pathInfo[10].split("_")[0]
    step = pathInfo[11].split("_")[0]
    week, rel_sec = cmsswIB2Week(release)
    index = "ib-matrix-" + week
    document = "runTheMatrix-data"
    id = sha1((release + architecture + workflow + str(step)).encode()).hexdigest()
    logdir = "/".join(logFile.split("/")[:-1])
    cmdfile = logdir + "/cmdLog"
    cmd_step = find_step_cmd(cmdfile, step)
    if cmd_step:
        payload["command"] = cmd_step
    wf_log = logdir + "/workflow.log"
    exitcode = get_exit_code(wf_log, int(step[-1]))
    if exitcode != -1:
        payload["exitcode"] = exitcode
    payload["workflow"] = workflow
    payload["release"] = release
    payload["architecture"] = architecture
    payload["step"] = step
    payload["@timestamp"] = timestp
    hostFile = "/".join(logFile.split("/")[:-1]) + "/hostname"
    if os.path.exists(hostFile):
        with open(hostFile, "r") as hname:
            payload["hostname"] = hname.readlines()[0].strip()
    exception = ""
    error = ""
    errors = []
    inException = False
    inError = False
    datasets = []
    error_count = 0
    if exists(logFile):
        with open(logFile) as f:
            lines = f.readlines()
        payload["url"] = (
            "https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/"
            + pathInfo[4]
            + "/"
            + pathInfo[8]
            + "/pyRelValMatrixLogs/run/"
            + pathInfo[-2]
            + "/"
            + pathInfo[-1]
        )
        total_lines = len(lines)
        for i in range(total_lines):
            l = lines[i].strip()
            if " Initiating request to open file " in l:
                try:
                    rootfile = l.split(" Initiating request to open file ")[1].split(" ")[0]
                    if (not "file:" in rootfile) and (not rootfile in datasets):
                        # if (i+2)<total_lines:
                        #  if (rootfile in lines[i+1]) and (rootfile in lines[i+2]) and ("Successfully opened file " in lines[i+1]) and ("Closed file " in lines[i+2]):
                        #    print "File read with no valid events: %s" % rootfile
                        #    continue
                        datasets.append(rootfile)
                except:
                    pass
                continue
            if l.startswith("----- Begin Fatal Exception"):
                inException = True
                continue
            if l.startswith("----- End Fatal Exception"):
                inException = False
                continue
            if l.startswith("%MSG-e"):
                inError = True
                error = l
                error_kind = re.split(" [0-9a-zA-Z-]* [0-9:]{8} CET", error)[0].replace(
                    "%MSG-e ", ""
                )
                continue
            if inError == True and l.startswith("%MSG"):
                inError = False
                if len(errors) < 10:
                    errors.append({"error": error, "kind": error_kind})
                error_count += 1
                error = ""
                error_kind = ""
                continue
            if inException:
                exception += l + "\n"
            if inError:
                error += l + "\n"
    if exception:
        payload["exception"] = exception
    if errors:
        payload["errors"] = errors
    payload["error_count"] = error_count
    try:
        payload = es_parse_jobreport(payload, logFile)
    except Exception as e:
        print(e)
    try:
        send_payload(index, document, id, json.dumps(payload))
    except:
        pass
    if datasets:
        dataset = {"type": "relvals", "name": "%s/%s" % (payload["workflow"], payload["step"])}
        for fld in ["release", "architecture", "@timestamp"]:
            dataset[fld] = payload[fld]
        for ds in datasets:
            ds_items = ds.split("?", 1)
            ds_items.append("")
            ibeos = "/store/user/cmsbuild"
            if ibeos in ds_items[0]:
                ds_items[0] = ds_items[0].replace(ibeos, "")
            else:
                ibeos = ""
            dataset["protocol"] = ds_items[0].split("/store/", 1)[0] + ibeos
            dataset["protocol_opts"] = ds_items[1]
            dataset["lfn"] = "/store/" + ds_items[0].split("/store/", 1)[1].strip()
            idx = sha1((id + ds).encode()).hexdigest()
            send_payload("ib-dataset-" + week, "relvals-dataset", idx, json.dumps(dataset))


if __name__ == "__main__":
    print("Processing ", sys.argv[1])
    es_parse_log(sys.argv[1])
