#! /usr/bin/env python3

import sys
import json
import os


def diff_from(metrics, data, dest, res):
    for metric in metrics:
        dmetric = dest[metric] - data[metric]
        dkey = "%s_diff" % metric
        res[dkey] = dmetric
        pdmetric = 0.0
        if not dest[metric] == 0.0:
            pdmetric = 100 * dmetric / dest[metric]
        pdkey = "%s_pdiff" % metric
        res[pdkey] = pdmetric


if len(sys.argv) == 1:
    print(
        """Usage: resources-diff.py FILE1 FILE2
Diff the content of two "resources.json" files and print the result to standard output."""
    )
    sys.exit(1)

with open(sys.argv[1]) as f:
    output = json.load(f)

metrics = [label for resource in output["resources"] for label in resource]

datamap = {module["type"] + "|" + module["label"]: module for module in output["modules"]}

for arg in sys.argv[2:]:
    with open(arg) as f:
        input = json.load(f)

    if output["resources"] != input["resources"]:
        print("Error: input files describe different metrics")
        sys.exit(1)

    if output["total"]["label"] != input["total"]["label"]:
        print("Warning: input files describe different process names")
    results = {}
    results["resources"] = []
    for resource in input["resources"]:
        for k,v in resource.items():
            dkey = "%s_diff" % k
            pdkey = "%s_pdiff" % k
            results["resources"].append({dkey: "%s diff" % v})
            results["resources"].append({pdkey:"%s percentage diff" % v})
    results["total"] = {}
    results["total"]["label"] = input["total"]["label"]
    results["total"]["events"] = input["total"]["events"]
    results["total"]["type"] = input["total"]["type"]
    results["modules"] = []
    diff_from(metrics, input["total"], output["total"] , results["total"])

    for module in input["modules"]:
        key = module["type"] + "|" + module["label"]
        result = {}
        result["type"] = module["type"]
        result["label"] = module["label"]
        result["events"] = module["events"]
        if key in datamap:
            diff_from(metrics, module, datamap[key], result)
            results["modules"].append(result)
        else:
            datamap[key] = module
            results["modules"].append(datamap[key])
dumpfile = os.path.dirname(sys.argv[1]) + "/diff-" + os.path.basename(sys.argv[1])
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)
