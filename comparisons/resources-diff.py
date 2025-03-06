#! /usr/bin/env python3

import sys
import json
import os


def diff_from(metrics, data, data_total, dest, dest_total, res):
    for metric in metrics:
        dmetric = dest[metric] - data[metric]
        dkey = "%s_diff" % metric
        res[dkey] = dmetric
        pdmetric = 0.0
        pdmetric = dmetric
        pdkey = "%s_pdiff" % metric
        res[pdkey] = pdmetric
        fkey = "%s_frac" % metric
        fdest = 100 * dest[metric] / dest_total[metric]
        dest[fkey] = fdest
        fdata = 100 * data[metric] / data_total[metric]
        data[fkey] = fdata
        dfmetric = fdest - fdata
        dfkey = "%s_frac_diff" % metric
        res[dfkey] = dfmetric
        pdfmetric = 0.0
        pdfmetric = dfmetric
        dkpkey = "%s_frac_diff" % metric
        res[dkpkey] = pdfmetric


if len(sys.argv) == 1:
    print(
        """Usage: resources-diff.py IB_FILE PR_FILE
Diff the content of two "resources.json" files and print the result to standard output."""
    )
    sys.exit(1)

with open(sys.argv[1]) as f:
    ibdata = json.load(f)

metrics = []
for resource in ibdata["resources"]:
    if "name" in resource:
        metrics.append(resource["name"])
    else:
        for key in resource:
            metrics.append(key)

datamapib = {module["type"] + "|" + module["label"]: module for module in ibdata["modules"]}

datacumulsib = {}
for module in ibdata["modules"]:
    datacumul = datacumulsib.get(module["type"])
    if datacumul:
        datacumul["count"] += 1
        for metric in metrics:
            datacumul[metric] += module[metric]
    else:
        datacumul = {}
        datacumul["count"] = 1
        for metric in metrics:
            datacumul[metric] = module[metric]
        datacumulsib[module["type"]] = datacumul

with open(sys.argv[2]) as f:
    prdata = json.load(f)
if ibdata["resources"] != prdata["resources"]:
    print("Error: input files describe different metrics")
    sys.exit(1)

datamappr = {module["type"] + "|" + module["label"]: module for module in prdata["modules"]}

datacumulspr = {}
for module in prdata["modules"]:
    datacumul = datacumulspr.get(module["type"])
    if datacumul:
        datacumul["count"] += 1
        for metric in metrics:
            datacumul[metric] += module[metric]
    else:
        datacumul = {}
        datacumul["count"] = 1
        for metric in metrics:
            datacumul[metric] = module[metric]
        datacumulspr[module["type"]] = datacumul
# print(datacumulspr)

if ibdata["total"]["label"] != prdata["total"]["label"]:
    print("Warning: input files describe different process names")

results = {}
results["resources"] = []
for resource in prdata["resources"]:
    for k, v in resource.items():
        dkey = "%s_diff" % k
        results["resources"].append({k: "%s" % v})
        results["resources"].append({dkey: "%s diff" % v})

results["total"] = {}
results["total"]["type"] = prdata["total"]["type"]
results["total"]["label"] = prdata["total"]["label"]
results["total"]["events"] = prdata["total"]["events"]
diff_from(
    metrics, ibdata["total"], ibdata["total"], prdata["total"], prdata["total"], results["total"]
)

results["modules"] = []
for module in prdata["modules"]:
    key = module["type"] + "|" + module["label"]
    result = {}
    result["type"] = module["type"]
    result["label"] = module["label"]
    result["events"] = module["events"]
    if key in datamapib:
        diff_from(metrics, datamapib[key], ibdata["total"], module, prdata["total"], result)
        results["modules"].append(result)
    else:
        datamapib[key] = module
        diff_from(metrics, datamapib[key], ibdata["total"], module, prdata["total"], result)
        results["modules"].append(result)

datamapres = {module["type"] + "|" + module["label"]: module for module in results["modules"]}


threshold = 5.0
error_threshold = 20.0


summaryLines = []
summaryLines += [
    "<html>",
    "<head><style>",
    "table, th, td {border: 1px solid black;}</style>",
    "<style> th, td {padding: 15px;}</style></head>",
    "<body><h3>FastTimerService Resources Difference</h3><table>",
    '</table><table><tr><td bgcolor="orange">',
    "warn threshold %0.2f" % threshold,
    '</td></tr><tr><td bgcolor="red">',
    "error threshold %0.2f" % error_threshold,
    '</td></tr><tr><td bgcolor="green">',
    "warn threshold -%0.2f" % threshold,
    '</td></tr><tr><td bgcolor="cyan">',
    "warn threshold -%0.2f" % error_threshold,
    "</td></tr>",
    "<tr><td>metric:<BR>&lt;baseline&gt;<BR>&lt;pull request&gt;<BR>&lt;PR - baseline&gt; </td>",
    "</tr></table>",
    "<table>",
    '<tr><td align="center">Type</td>',
    '<td align="center">Label</td>',
    '<td align="center">real time</td>',
    '<td align="center">cpu time</td>',
    '<td align="center">allocated memory </td>',
    '<td align="center">deallocated memory </td>',
    '<td align="center">events</td>',
    "</tr>",
    "<td>%s</td>" % prdata["total"]["type"],
    "<td>%s</td>" % prdata["total"]["label"],
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["time_real"],
        prdata["total"]["time_real"],
        results["total"]["time_real_diff"],
    ),
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["time_thread"],
        prdata["total"]["time_thread"],
        results["total"]["time_thread_diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["mem_alloc"],
        prdata["total"]["mem_alloc"],
        results["total"]["mem_alloc_diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["mem_free"],
        prdata["total"]["mem_free"],
        results["total"]["mem_free_diff"],
    ),
    "<td>%i<br>%i<br>%i</td>"
    % (ibdata["total"]["events"], prdata["total"]["events"], results["total"]["events"]),
    "</tr></table>",
    '<table><tr><td align="center">Module type</td>',
    '<td align="center">Module label</td>',
    '<td align="center">real time</td>',
    '<td align="center">percentage total<br>real time</td>',
    '<td align="center">cpu time</td>',
    '<td align="center">percentage total<br>cpu time</td>',
    '<td align="center">allocated memory</td>',
    '<td align="center">deallocated memory</td>',
    '<td align="center">events</td>',
    "</tr>",
]


for item in sorted(datamapres.items(), key=lambda x: x[1]["time_thread_frac_diff"], reverse=True):
    key = item[1]["type"] + "|" + item[1]["label"]
    if not key == "|":
        moduleib = datamapib[key]
        modulepr = datamappr[key]
        moduleres = datamapres[key]
        cellString = '<td align="right" '
        color = ""
        if moduleres["time_thread_frac_diff"] > threshold:
            color = 'bgcolor="orange"'
        if moduleres["time_thread_frac_diff"] > error_threshold:
            color = 'bgcolor="red"'
        if moduleres["time_thread_frac_diff"] < -1.0 * threshold:
            color = 'bgcolor="cyan"'
        if moduleres["time_thread_frac_diff"] < -1.0 * error_threshold:
            color = 'bgcolor="green"'
        cellString += color
        cellString += ">"
        summaryLines += [
            "<tr>",
            "<td> %s</td>" % moduleres["type"],
            "<td> %s</td>" % moduleres["label"],
            '<td align="right"> %0.2f<br> %0.2f<br> %0.2f</td>'
            % (
                moduleib["time_real"],
                modulepr["time_real"],
                moduleres["time_real_diff"],
            ),
            '<td align="right"> %0.2f%%<br> %0.2f%%<br> %0.2f%%</td>'
            % (
                moduleib["time_real_frac"],
                modulepr["time_real_frac"],
                moduleres["time_real_frac_diff"],
            ),
            '<td align="right"> %0.2f<br> %0.2f<br> %0.2f</td>'
            % (
                moduleib["time_thread"],
                modulepr["time_thread"],
                moduleres["time_thread_diff"],
            ),
            cellString
            + "%0.2f%%<br> %0.2f%%<br> %0.2f%%</td>"
            % (
                moduleib["time_thread_frac"],
                modulepr["time_thread_frac"],
                moduleres["time_thread_frac_diff"],
            ),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (moduleib["mem_alloc"], modulepr["mem_alloc"], moduleres["mem_alloc_diff"]),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (moduleib["mem_free"], modulepr["mem_free"], moduleres["mem_free_diff"]),
            "<td>%i<br>%i<br>%i</td>"
            % (moduleib["events"], modulepr["events"], moduleres["events"]),
            "</tr>",
        ]

summaryLines += []
summaryLines += ["</body></html>"]

summaryFile = os.path.dirname(sys.argv[2]) + "/diff-" + os.path.basename(sys.argv[2]) + ".html"
with open(summaryFile, "w") as g:
    for summaryLine in summaryLines:
        print(summaryLine, file=g)

dumpfile = os.path.dirname(sys.argv[2]) + "/diff-" + os.path.basename(sys.argv[2])
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)
