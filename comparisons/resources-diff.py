#! /usr/bin/env python3

import sys
import json
import os


def diff_from(metrics, data, dest, res):
    #    ratio = 0.0
    #    if not dest["events"] == 0:
    #      ratio = data["events"]/dest["events"]
    #    data["events"] = ratio * dest["events"]
    for metric in metrics:
        dmetric = dest[metric] - data[metric]
        dkey = "%s_diff" % metric
        res[dkey] = dmetric
        pdmetric = 0.0
        if not dest[metric] == 0.0:
            pdmetric = 100 * dmetric / dest[metric]
        pdkey = "%s_pdiff" % metric
        res[pdkey] = pdmetric


#        data[metric] = ratio * dest[metric]


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

with open(sys.argv[2]) as f:
    input = json.load(f)
if output["resources"] != input["resources"]:
    print("Error: input files describe different metrics")
    sys.exit(1)

datamap2 = {module["type"] + "|" + module["label"]: module for module in input["modules"]}

if output["total"]["label"] != input["total"]["label"]:
    print("Warning: input files describe different process names")
results = {}
results["resources"] = []
for resource in input["resources"]:
    for k, v in resource.items():
        dkey = "%s_diff" % k
        pdkey = "%s_pdiff" % k
        results["resources"].append({dkey: "%s diff" % v})
        results["resources"].append({pdkey: "%s percentage diff" % v})
results["total"] = {}
results["total"]["label"] = input["total"]["label"]
results["total"]["events"] = input["total"]["events"]
results["total"]["type"] = input["total"]["type"]
results["modules"] = []

diff_from(metrics, input["total"], output["total"], results["total"])

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
        diff_from(metrics, module, datamap[key], result)
        results["modules"].append(result)

datamap3 = {module["type"] + "|" + module["label"]: module for module in results["modules"]}

threshold = 1.0
error_threshold = 10.0


summaryLines = []
summaryLines += [
    "<html>",
    "<head><style>"
    + "table, th, td {border: 1px solid black;}</style>"
    + "<style> th, td {padding: 15px;}</style></head>",
    "<body><h3>FastTimerService Resources Difference</h3><table>",
    '</table><table><tr><td bgcolor="orange">'
    + "warn threshold %0.2f" % threshold
    + '%</td><td></td></tr><tr><td bgcolor="red">'
    + "error threshold %0.2f" % error_threshold
    + "%</td><td></td></tr>",
    "<tr><td>metric:<BR>&lt;pull request &gt;<BR>&lt;baseline&gt;<BR>(PR - baseline)</td><td><br>&lt;100* (PR - baseline)/baseline&gt;<br></td></tr></table><table>",
    '<tr><td align="center">Module type</td>'
    + '<td align="center">Module label</td>'
    + '<td align="center">real time diff</td>'
    + '<td align="center">real time percent diff</td>'
    + '<td align="center">cpu time diff</td>'
    + '<td align="center">cpu time percent diff</td>'
    + '<td align="center">allocated memory diff</td>'
    + '<td align="center">allocated memory percent diff</td>'
    + '<td align="center">deallocated memory diff</td>'
    + '<td align="center">deallocated memory percent diff</td>'
    + '<td align="center">events</td>'
    + "</tr>",
]


for key in sorted(datamap3.keys()):
    if not key == "|":
        module1 = datamap[key]
        module2 = datamap2[key]
        module3 = datamap3[key]
        cellString = '<td align="right" '
        color = ""
        if abs(module3["time_thread_pdiff"]) > threshold:
            color = 'bgcolor="orange"'
        if abs(module3["time_thread_pdiff"]) > error_threshold:
            color = 'bgcolor="red"'
        cellString += color
        cellString += ">"
        summaryLines += [
            "<tr>"
            + "<td>%s</td>" % module3["type"]
            + "<td>%s</td>" % module3["label"]
            + '<td align="right">%0.4f<br>%0.4f<br>%0.4f</td>'
            % (module1["time_real"], module2["time_real"], module3["time_real_diff"])
            + '<td align="right">%0.2f%%</td>' % module3["time_real_pdiff"]
            + '<td align="right">%0.4f<br>%0.4f<br>%0.4f</td>'
            % (module1["time_thread"], module2["time_thread"], module3["time_thread_diff"])
            + cellString
            + "%0.2f%%</td>" % module3["time_thread_pdiff"]
            + '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (module1["mem_alloc"], module2["mem_alloc"], module3["mem_alloc_diff"])
            + '<td align="right">%0.2f%%</td>' % module3["mem_alloc_pdiff"]
            + '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (module1["mem_free"], module2["mem_free"], module3["mem_free_diff"])
            + '<td align="right">%0.2f%%</td>' % module3["mem_free_pdiff"]
            + "<td>%i<br>%i<br>%i</td>" % (module1["events"], module2["events"], module3["events"])
            + "</tr>"
        ]
summaryLines += ["</table></body></html>"]

summaryFile = os.path.dirname(sys.argv[1]) + "/diff-" + os.path.basename(sys.argv[1]) + ".html"
with open(summaryFile, "w") as g:
    for summaryLine in summaryLines:
        print(summaryLine, file=g)

dumpfile = os.path.dirname(sys.argv[1]) + "/diff-" + os.path.basename(sys.argv[1])
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)
