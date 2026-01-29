#! /usr/bin/env python3

import sys
import json
import os


def diff_from(metrics, data, data_total, dest, dest_total, res):
    for metric in metrics:
        dmetric = dest[metric] - data[metric]
        dkey = "%s diff" % metric
        res[dkey] = dmetric
        pdmetric = 0.0
        pdmetric = dmetric
        pdkey = "%s pdiff" % metric
        res[pdkey] = pdmetric
        fkey = "%s frac" % metric
        fdest = 100 * dest[metric] / dest_total[metric] if dest_total[metric] != 0 else 0.0
        dest[fkey] = fdest
        fdata = 100 * data[metric] / data_total[metric] if data_total[metric] != 0 else 0.0
        data[fkey] = fdata
        dfmetric = fdest - fdata
        dfkey = "%s frac diff" % metric
        res[dfkey] = dfmetric
        pdfmetric = 0.0
        pdfmetric = dfmetric
        dkpkey = "%s frac diff" % metric
        res[dkpkey] = pdfmetric


if len(sys.argv) == 1:
    print("""Usage: resources-diff.py IB_FILE PR_FILE
Diff the content of two "resources.json" files and print the result to standard output.""")
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

datamapib = {
    module["label"] + "|" + module["type"] + "|" + module["record"]: module
    for module in ibdata["modules"]
}

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

datamappr = {
    module["label"] + "|" + module["type"] + "|" + module["record"]: module
    for module in prdata["modules"]
}

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
        dkey = "%s diff" % k
        results["resources"].append({k: "%s" % v})
        results["resources"].append({dkey: "%s diff" % v})

results["total"] = {}
results["total"]["type"] = prdata["total"]["type"]
results["total"]["label"] = prdata["total"]["label"]

diff_from(
    metrics, ibdata["total"], ibdata["total"], prdata["total"], prdata["total"], results["total"]
)

results["modules"] = []
for module in prdata["modules"]:
    key = module["label"] + "|" + module["type"] + "|" + module["record"]
    result = {}
    result["type"] = module["type"]
    result["label"] = module["label"]
    result["record"] = module["record"]
    result["transitions"] = module["transitions"]
    if key in datamapib:
        diff_from(metrics, datamapib[key], ibdata["total"], module, prdata["total"], result)
        results["modules"].append(result)
    else:
        datamapib[key] = module
        diff_from(metrics, datamapib[key], ibdata["total"], module, prdata["total"], result)
        results["modules"].append(result)

datamapres = {
    module["label"] + "|" + module["type"] + "|" + module["record"]: module
    for module in results["modules"]
}

threshold = 5000.0
error_threshold = 20000.0


summaryLines = []
summaryLines += [
    "<html>",
    "<head><style>",
    "table, th, td {border: 1px solid black;}</style>",
    "<style> th, td {padding: 15px;}</style></head>",
    "<body><h3>ModuleAllocMonitor Resources Difference</h3><table>",
    '</table><table><tr><td bgcolor="orange">',
    "warn threshold %0.2f kB" % threshold,
    '</td></tr><tr><td bgcolor="red">',
    "error threshold %0.2f kB" % error_threshold,
    '</td></tr><tr><td bgcolor="green">',
    "warn threshold -%0.2f kB" % threshold,
    '</td></tr><tr><td bgcolor="cyan">',
    "warn threshold -%0.2f kB" % error_threshold,
    "</td></tr>",
    "<tr><td>metric:<BR>&lt;baseline&gt;<BR>&lt;pull request&gt;<BR>&lt;PR - baseline&gt; </td>",
    "</tr></table>",
    "<table>",
    '<tr><td align="center">Type<BR>Label</td>',
    '<td align="center">added construction</td>',
    '<td align="center">added event</td>',
    '<td align="center">added event setup</td>',
    '<td align="center">nAlloc construction</td>',
    '<td align="center">nAlloc event</td>',
    '<td align="center">nAlloc event setup</td>',
    "</tr>",
    "<td>%s<BR>%s</td>" % (prdata["total"]["type"], prdata["total"]["label"]),
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["added construction"],
        prdata["total"]["added construction"],
        results["total"]["added construction diff"],
    ),
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["added event"],
        prdata["total"]["added event"],
        results["total"]["added event diff"],
    ),
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["added event setup"],
        prdata["total"]["added event setup"],
        results["total"]["added event setup diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["nAlloc construction"],
        prdata["total"]["nAlloc construction"],
        results["total"]["nAlloc construction diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["nAlloc event"],
        prdata["total"]["nAlloc event"],
        results["total"]["nAlloc event diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["nAlloc event setup"],
        prdata["total"]["nAlloc event setup"],
        results["total"]["nAlloc event setup diff"],
    ),
    "</tr></table>",
    '<table><tr><td align="center">Module label<BR>Module type<BR>Module record</td>',
    '<td align="center">added construction (kB)</td>',
    '<td align="center">added event (kB)</td>',
    '<td align="center">added event setup (kB)</td>',
    '<td align="center">added total (kB)</td>',
    '<td align="center">nAlloc construction</td>',
    '<td align="center">nAlloc event</td>',
    '<td align="center">nAlloc event setup</td>',
    '<td align="center">nAlloc total</td>',
    '<td align="center">transitions</td>',
    "</tr>",
]

for item in sorted(
    datamapres.items(),
    key=lambda x: x[1]["added construction diff"]
    + x[1]["added event diff"]
    + x[1]["added event setup diff"],
    reverse=True,
):
    key = item[1]["label"] + "|" + item[1]["type"] + "|" + item[1]["record"]
    if not key == "||":
        moduleib = datamapib[key]
        modulepr = datamappr[key]
        moduleres = datamapres[key]
        cellString = '<td align="right" '
        color = ""
        added_total_pr = (
            modulepr.get("added event setup", 0)
            + modulepr.get("added event", 0)
            + modulepr.get("added construction", 0)
        )
        added_total_ib = (
            moduleib.get("added event setup", 0)
            + moduleib.get("added event", 0)
            + moduleib.get("added construction", 0)
        )
        added_total_diff = (
            moduleres.get("added event setup diff", 0)
            + moduleres.get("added event diff", 0)
            + moduleres.get("added construction diff", 0)
        )
        if added_total_diff > threshold:
            color = 'bgcolor="orange"'
        if added_total_diff > error_threshold:
            color = 'bgcolor="red"'
        if added_total_diff < -1.0 * threshold:
            color = 'bgcolor="cyan"'
        if added_total_diff < -1.0 * error_threshold:
            color = 'bgcolor="green"'
        cellString += color
        cellString += ">"
        summaryLines += [
            "<tr>",
            "<td>%s<BR>%s<BR> %s</td>"
            % (moduleres["label"], moduleres["type"], moduleres["record"]),
            '<td align="right"> %0.2f<br> %0.2f<br> %0.2f</td>'
            % (
                moduleib["added construction"],
                modulepr["added construction"],
                moduleres["added construction diff"],
            ),
            '<td align="right"> %0.2f<br> %0.2f<br> %0.2f</td>'
            % (
                moduleib["added event"],
                modulepr["added event"],
                moduleres["added event diff"],
            ),
            '<td align="right"> %0.2f<br> %0.2f<br> %0.2f</td>'
            % (
                moduleib["added event setup"],
                modulepr["added event setup"],
                moduleres["added event setup diff"],
            ),
            cellString
            + "%0.2f<br> %0.2f<br> %0.2f</td>"
            % (
                added_total_ib,
                added_total_pr,
                added_total_diff,
            ),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (
                moduleib["nAlloc construction"],
                modulepr["nAlloc construction"],
                moduleres["nAlloc construction diff"],
            ),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (moduleib["nAlloc event"], modulepr["nAlloc event"], moduleres["nAlloc event diff"]),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (
                moduleib["nAlloc event setup"],
                modulepr["nAlloc event setup"],
                moduleres["nAlloc event setup diff"],
            ),
            '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
            % (
                moduleib["nAlloc event setup"]
                + moduleib["nAlloc event"]
                + moduleib["nAlloc construction"],
                modulepr["nAlloc event setup"]
                + modulepr["nAlloc event"]
                + modulepr["nAlloc construction"],
                moduleres["nAlloc event setup diff"]
                + moduleres["nAlloc event diff"]
                + moduleres["nAlloc construction diff"],
            ),
            "<td>%i<br>%i<br>%i</td>"
            % (moduleib["transitions"], modulepr["transitions"], moduleres["transitions"]),
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
