#! /usr/bin/env python
from __future__ import print_function
from optparse import OptionParser
from os import listdir
from os import path
import re
import json

# ------------------------------------------------------------------------------------------------------------
# This script reads a list of the workflows, steps and parameters for which you want to see the graphs
# It generates a json file with the correct structure and links to each graph, this json file is used
# to create the visualization
# ------------------------------------------------------------------------------------------------------------


def get_wfs_ordered(base_dir):
    workflows = {}
    check = re.compile("^[0-9]+.")
    for wf in listdir(base_dir):
        if check.match(wf):
            wf_number = float(re.sub("_.*$", "", wf))
            workflows[wf_number] = wf
    return [workflows[wf_number] for wf_number in sorted(workflows.keys())]


def add_images_to_step(wf, step):
    imgs = []
    for img_name in listdir("%s/%s/%s" % (BASE_DIR, wf["wf_name"], step["step_name"])):
        if img_name in RESULT_FILE_NAMES:
            img = {}
            img["name"] = img_name
            img["url"] = "%s/%s/%s/%s" % (BASE_URL, wf["wf_name"], step["step_name"], img["name"])
            imgs.append(img)
            print(img["name"])
    step["imgs"] = imgs


def add_steps_to_wf(wf):
    steps = []
    for step_name in sorted(listdir("%s/%s" % (BASE_DIR, wf["wf_name"]))):
        if path.isdir("%s/%s/%s" % (BASE_DIR, wf["wf_name"], step_name)):
            step = {}
            step["step_name"] = step_name
            add_images_to_step(wf, step)
            steps.append(step)
            print(step_name)
    wf["steps"] = steps


def get_workflows():
    workflows = []
    for wf_name in get_wfs_ordered(BASE_DIR):
        if path.isdir("%s/%s/" % (BASE_DIR, wf_name)) and not "bootstrap" in wf_name:
            print("Adding %s" % wf_name)
            wf = {}
            wf["wf_name"] = wf_name
            add_steps_to_wf(wf)
            workflows.append(wf)
            print()
    return workflows


def print_workflows(wfs):
    for wf in wfs:
        print(wf["wf_name"])
        for step in wf["steps"]:
            print("\t %s" % step["step_name"])
            for img in step["imgs"]:
                print(img)


def add_workflow(results, wf_name):
    for wf in results["wfs"]:
        if wf["wf_name"] == wf_name:
            return wf

    new_wf = {}
    new_wf["wf_name"] = wf_name
    results["wfs"].append(new_wf)
    return new_wf


def add_step(workflow, step_name):
    if not workflow.get("steps"):
        workflow["steps"] = []

    for step in workflow["steps"]:
        if step["step_name"] == step_name:
            return step

    new_step = {}
    new_step["step_name"] = step_name
    workflow["steps"].append(new_step)
    return new_step


def add_param(step, param_name):
    if not step.get("imgs"):
        step["imgs"] = []

    for p in step["imgs"]:
        if p["name"] == param_name:
            return p

    new_param = {}
    new_param["name"] = param_name
    step["imgs"].append(new_param)
    return new_param


def add_url_to_param(workflow, step, param):
    step_number = step["step_name"].split("_")[0]
    url = (
        BASE_URL.replace("WORKFLOW", workflow["wf_name"])
        .replace("STEP", step_number)
        .replace("PARAM", param["name"])
    )
    url = url.replace("+", "%2B")
    print(url)
    param["url"] = url


# -----------------------------------------------------------------------------------
# ---- Parser Options
# -----------------------------------------------------------------------------------
parser = OptionParser(
    usage="usage: %prog PLOTS_LIST \n PLOTS_LIST list of plots that you want to visualize"
)

(options, args) = parser.parse_args()

# -----------------------------------------------------------------------------------
# ---- Start
# -----------------------------------------------------------------------------------

if len(args) < 1:
    print("you need to specify a list of plots")
    parser.print_help()
    exit()

WF_LIST = args[0]

GRAPH_PARAMS = "&from=-15days&fontBold=true&fontSize=12&lineWidth=5&title=PARAM&yMin=0"

BASE_URL = (
    "https://cmsgraph.cern.ch/render?target=IBRelVals.slc6_amd64_gcc481.CMSSW_7_1_X.WORKFLOW.STEP.PARAM&height=800&width=800%s"
    % GRAPH_PARAMS
)

result = {}

lines = open(WF_LIST, "r").readlines()

result["wfs"] = []

for l in lines:
    if l.startswith("#"):
        continue
    else:
        l = l.replace("\n", "")
        parts = l.split(" ")
        wf_name = parts[0]
        step_name = parts[1]
        param_name = parts[2]

        workflow = add_workflow(result, wf_name)
        step = add_step(workflow, step_name)
        param = add_param(step, param_name)
        add_url_to_param(workflow, step, param)

print(result)

out_json = open("plots_summary.json", "w")
json.dump(result, out_json, indent=4)
out_json.close()
