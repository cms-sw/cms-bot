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

selectable_metrics = [
    ("added_construction", "added construction (kB)"),
    ("added_begin_run", "added begin run (kB)"),
    ("added_begin_lumi", "added begin luminosity block (kB)"),
    ("added_event", "added event (kB)"),
    ("added_event_setup", "added event setup (kB)"),
    ("added_total", "added total (kB)"),
    ("nalloc_construction", "nAlloc construction"),
    ("nalloc_begin_run", "nAlloc begin run"),
    ("nalloc_begin_lumi", "nAlloc begin luminosity block"),
    ("nalloc_event", "nAlloc event"),
    ("nalloc_event_setup", "nAlloc event setup"),
    ("nalloc_total", "nAlloc total"),
    ("transitions", "transitions"),
]

selector_options = "".join(
    ['<option value="%s">%s</option>' % (metric_key, metric_name) for metric_key, metric_name in selectable_metrics]
)
js_threshold = "%0.2f" % threshold
js_error_threshold = "%0.2f" % error_threshold


summaryLines = []
summaryLines += [
    "<html>",
    "<head><style>",
    "table, th, td {border: 1px solid black;}</style>",
    "<style> th, td {padding: 15px;}</style>",
    "<script>",
    "function sortTable(table, column) {",
    "    var colIndex = column - 1;",
    "    var rows = Array.prototype.slice.call(table.rows, 1);",
    "    var previousColumn = parseInt(table.getAttribute(\"data-sort-column\"), 10);",
    "    var previousDirection = table.getAttribute(\"data-sort-direction\") || \"desc\";",
    "    var direction = \"desc\";",
    "    if (!isNaN(previousColumn) && previousColumn === colIndex) {",
    "        direction = previousDirection === \"desc\" ? \"asc\" : \"desc\";",
    "    }",
    "",
    "    rows.sort(function(a, b) {",
    "        var xCell = a.getElementsByTagName(\"td\")[colIndex];",
    "        var yCell = b.getElementsByTagName(\"td\")[colIndex];",
    "        var xText = xCell ? xCell.textContent.trim() : \"\";",
    "        var yText = yCell ? yCell.textContent.trim() : \"\";",
    "",
    "        var xNum = Number(xText);",
    "        var yNum = Number(yText);",
    "        var xIsNum = xText !== \"\" && !isNaN(xNum);",
    "        var yIsNum = yText !== \"\" && !isNaN(yNum);",
    "",
    "        var cmp = 0;",
    "        if (xIsNum && yIsNum) {",
    "            cmp = xNum - yNum;",
    "        } else {",
    "            cmp = xText.localeCompare(yText);",
    "        }",
    "        return direction === \"asc\" ? cmp : -cmp;",
    "    });",
    "",
    "    for (var i = 0; i < rows.length; i++) {",
    "        table.appendChild(rows[i]);",
    "    }",
    "",
    "    table.setAttribute(\"data-sort-column\", colIndex);",
    "    table.setAttribute(\"data-sort-direction\", direction);",
    "}",
    "function updateMetricColumn() {",
    "    var selector = document.getElementById(\"metricSelector\");",
    "    if (!selector) return;",
    "    var selectedMetric = selector.value;",
    "    var cells = document.getElementsByClassName(\"selectedMetric\");",
    "    for (var i = 0; i < cells.length; i++) {",
    "        var metrics = JSON.parse(cells[i].getAttribute(\"data-metrics\") || \"{}\");",
    "        var diffs = JSON.parse(cells[i].getAttribute(\"data-diffs\") || \"{}\");",
    "        cells[i].innerHTML = metrics[selectedMetric] || \"\";",
    "        cells[i].removeAttribute(\"bgcolor\");",
    "        var diffValue = Number(diffs[selectedMetric]);",
    "        if (!isNaN(diffValue)) {",
    "            if (diffValue > %s) {" % js_error_threshold,
    "                cells[i].setAttribute(\"bgcolor\", \"red\");",
    "            } else if (diffValue > %s) {" % js_threshold,
    "                cells[i].setAttribute(\"bgcolor\", \"orange\");",
    "            } else if (diffValue < -1.0 * %s) {" % js_error_threshold,
    "                cells[i].setAttribute(\"bgcolor\", \"green\");",
    "            } else if (diffValue < -1.0 * %s) {" % js_threshold,
    "                cells[i].setAttribute(\"bgcolor\", \"cyan\");",
    "            }",
    "        }",
    "    }",
    "}",
    "document.addEventListener(\"DOMContentLoaded\", updateMetricColumn);",
    "</script>",
    "</head>",
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
    '<td align="center">added begin run</td>',
    '<td align="center">added begin luminosity block</td>',
    '<td align="center">added event</td>',
    '<td align="center">added event setup</td>',
    '<td align="center">nAlloc construction</td>',
    '<td align="center">nAlloc begin run</td>',
    '<td align="center">nAlloc begin luminosity block</td>',
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
        ibdata["total"]["added global begin run"] + ibdata["total"]["added stream begin run"],
        prdata["total"]["added global begin run"] + prdata["total"]["added stream begin run"],
        results["total"]["added global begin run diff"]
        + results["total"]["added stream begin run diff"],
    ),
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["added global begin luminosity block"]
        + ibdata["total"]["added stream begin luminosity block"],
        prdata["total"]["added global begin luminosity block"]
        + prdata["total"]["added stream begin luminosity block"],
        results["total"]["added global begin luminosity block diff"]
        + results["total"]["added stream begin luminosity block diff"],
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
        ibdata["total"]["nAlloc global begin run"] + ibdata["total"]["nAlloc stream begin run"],
        prdata["total"]["nAlloc global begin run"] + prdata["total"]["nAlloc stream begin run"],
        results["total"]["nAlloc global begin run diff"]
        + results["total"]["nAlloc stream begin run diff"],
    ),
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["nAlloc global begin luminosity block"]
        + ibdata["total"]["nAlloc stream begin luminosity block"],
        prdata["total"]["nAlloc global begin luminosity block"]
        + prdata["total"]["nAlloc stream begin luminosity block"],
        results["total"]["nAlloc global begin luminosity block diff"]
        + results["total"]["nAlloc stream begin luminosity block diff"],
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
    '<table id="moduleTable"><tr>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 1)">Module label</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 2)">Module type</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 3)">Module record</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 4)">Metric<BR><select id="metricSelector" onchange="updateMetricColumn()">%s</select></th>'
    % selector_options,
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 5)">added construction (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 6)">added construction (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 7)">added construction (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 8)">added begin run (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 9)">added begin run (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 10)">added begin run (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 11)">added begin luminosity block (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 12)">added begin luminosity block (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 13)">added begin luminosity block (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 14)">added event (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 15)">added event (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 16)">added event (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 17)">added event setup (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 18)">added event setup (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 19)">added event setup (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 20)">added total (kB) IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 21)">added total (kB) PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 22)">added total (kB) PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 23)">nAlloc construction IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 24)">nAlloc construction PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 25)">nAlloc construction PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 26)">nAlloc begin run IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 27)">nAlloc begin run PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 28)">nAlloc begin run PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 29)">nAlloc begin luminosity block IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 30)">nAlloc begin luminosity block PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 31)">nAlloc begin luminosity block PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 32)">nAlloc event IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 33)">nAlloc event PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 34)">nAlloc event PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 35)">nAlloc event setup IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 36)">nAlloc event setup PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 37)">nAlloc event setup PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 38)">nAlloc total IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 39)">nAlloc total PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 40)">nAlloc total PR - IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 41)">transitions IB</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 42)">transitions PR</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 43)">transitions PR - IB</th>',
    "</tr>",
]

for item in datamapres.items():
    key = item[1]["label"] + "|" + item[1]["type"] + "|" + item[1]["record"]
    if not key == "||":
        moduleib = datamapib[key]
        modulepr = datamappr[key]
        moduleres = datamapres[key]
        added_total_pr = (
            modulepr.get("added event setup", 0)
            + modulepr.get("added event", 0)
            + modulepr.get("added construction", 0)
            + modulepr.get("added global begin run", 0)
            + modulepr.get("added stream begin run", 0)
            + modulepr.get("added global begin luminosity block", 0)
            + modulepr.get("added stream begin luminosity block", 0)
        )
        modulepr["added total"] = added_total_pr
        added_total_ib = (
            moduleib.get("added event setup", 0)
            + moduleib.get("added event", 0)
            + moduleib.get("added construction", 0)
            + moduleib.get("added global begin run", 0)
            + moduleib.get("added stream begin run", 0)
            + moduleib.get("added global begin luminosity block", 0)
            + moduleib.get("added stream begin luminosity block", 0)
        )
        moduleib["added total"] = added_total_ib
        added_total_diff = (
            moduleres.get("added event setup diff", 0)
            + moduleres.get("added event diff", 0)
            + moduleres.get("added construction diff", 0)
            + moduleres.get("added global begin run diff", 0)
            + moduleres.get("added stream begin run diff", 0)
            + moduleres.get("added global begin luminosity block diff", 0)
            + moduleres.get("added stream begin luminosity block diff", 0)
        )
        moduleres["added total diff"] = added_total_diff

dumpfile = os.path.dirname(sys.argv[2]) + "./diff-" + os.path.basename(sys.argv[2])
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)

for item in sorted(
    datamapres.items(),
    key=lambda x: x[1]["added total diff"],
    reverse=True,
):
    key = item[1]["label"] + "|" + item[1]["type"] + "|" + item[1]["record"]
    if not key == "||":
        moduleib = datamapib[key]
        modulepr = datamappr[key]
        moduleres = datamapres[key]
        selected_metric_values = {
            "added_construction": "%0.2f<br>%0.2f<br>%0.2f"
            % (
                moduleib["added construction"],
                modulepr["added construction"],
                moduleres["added construction diff"],
            ),
            "added_begin_run": "%0.2f<br>%0.2f<br>%0.2f"
            % (
                moduleib["added global begin run"] + moduleib["added stream begin run"],
                modulepr["added global begin run"] + modulepr["added stream begin run"],
                moduleres["added global begin run diff"] + moduleres["added stream begin run diff"],
            ),
            "added_begin_lumi": "%0.2f<br>%0.2f<br>%0.2f"
            % (
                moduleib["added global begin luminosity block"]
                + moduleib["added stream begin luminosity block"],
                modulepr["added global begin luminosity block"]
                + modulepr["added stream begin luminosity block"],
                moduleres["added global begin luminosity block diff"]
                + moduleres["added stream begin luminosity block diff"],
            ),
            "added_event": "%0.2f<br>%0.2f<br>%0.2f"
            % (moduleib["added event"], modulepr["added event"], moduleres["added event diff"]),
            "added_event_setup": "%0.2f<br>%0.2f<br>%0.2f"
            % (
                moduleib["added event setup"],
                modulepr["added event setup"],
                moduleres["added event setup diff"],
            ),
            "added_total": "%0.2f<br>%0.2f<br>%0.2f"
            % (moduleib["added total"], modulepr["added total"], moduleres["added total diff"]),
            "nalloc_construction": "%i<br>%i<br>%i"
            % (
                moduleib["nAlloc construction"],
                modulepr["nAlloc construction"],
                moduleres["nAlloc construction diff"],
            ),
            "nalloc_begin_run": "%i<br>%i<br>%i"
            % (
                moduleib["nAlloc global begin run"] + moduleib["nAlloc stream begin run"],
                modulepr["nAlloc global begin run"] + modulepr["nAlloc stream begin run"],
                moduleres["nAlloc global begin run diff"] + moduleres["nAlloc stream begin run diff"],
            ),
            "nalloc_begin_lumi": "%i<br>%i<br>%i"
            % (
                moduleib["nAlloc global begin luminosity block"]
                + moduleib["nAlloc stream begin luminosity block"],
                modulepr["nAlloc global begin luminosity block"]
                + modulepr["nAlloc stream begin luminosity block"],
                moduleres["nAlloc global begin luminosity block diff"]
                + moduleres["nAlloc stream begin luminosity block diff"],
            ),
            "nalloc_event": "%i<br>%i<br>%i"
            % (moduleib["nAlloc event"], modulepr["nAlloc event"], moduleres["nAlloc event diff"]),
            "nalloc_event_setup": "%i<br>%i<br>%i"
            % (
                moduleib["nAlloc event setup"],
                modulepr["nAlloc event setup"],
                moduleres["nAlloc event setup diff"],
            ),
            "nalloc_total": "%i<br>%i<br>%i"
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
            "transitions": "%i<br>%i<br>%i"
            % (moduleib["transitions"], modulepr["transitions"], modulepr["transitions"] - moduleib["transitions"]),
        }
        selected_metric_diffs = {
            "added_construction": moduleres["added construction diff"],
            "added_begin_run": moduleres["added global begin run diff"] + moduleres["added stream begin run diff"],
            "added_begin_lumi": moduleres["added global begin luminosity block diff"]
            + moduleres["added stream begin luminosity block diff"],
            "added_event": moduleres["added event diff"],
            "added_event_setup": moduleres["added event setup diff"],
            "added_total": moduleres["added total diff"],
            "nalloc_construction": moduleres["nAlloc construction diff"],
            "nalloc_begin_run": moduleres["nAlloc global begin run diff"] + moduleres["nAlloc stream begin run diff"],
            "nalloc_begin_lumi": moduleres["nAlloc global begin luminosity block diff"]
            + moduleres["nAlloc stream begin luminosity block diff"],
            "nalloc_event": moduleres["nAlloc event diff"],
            "nalloc_event_setup": moduleres["nAlloc event setup diff"],
            "nalloc_total": moduleres["nAlloc event setup diff"]
            + moduleres["nAlloc event diff"]
            + moduleres["nAlloc construction diff"],
            "transitions": modulepr["transitions"] - moduleib["transitions"],
        }
        selected_metric_json = json.dumps(selected_metric_values).replace("'", "&apos;")
        selected_metric_diffs_json = json.dumps(selected_metric_diffs).replace("'", "&apos;")
        summaryLines += [
            "<tr>",
            '<td align="center">%s</td><td align="center">%s</td><td align="center">%s</td>'
            % (moduleres["label"], moduleres["type"], moduleres["record"]),
            '<td align="right" class="selectedMetric" data-metrics=\'%s\' data-diffs=\'%s\'></td>'
            % (selected_metric_json, selected_metric_diffs_json),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added construction"],
                modulepr["added construction"],
                moduleres["added construction diff"],
            ),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added global begin run"] + moduleib["added stream begin run"],
                modulepr["added global begin run"] + modulepr["added stream begin run"],
                moduleres["added global begin run diff"]
                + moduleres["added stream begin run diff"],
            ),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added global begin luminosity block"]
                + moduleib["added stream begin luminosity block"],
                modulepr["added global begin luminosity block"]
                + modulepr["added stream begin luminosity block"],
                moduleres["added global begin luminosity block diff"]
                + moduleres["added stream begin luminosity block diff"],
            ),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added event"],
                modulepr["added event"],
                moduleres["added event diff"],
            ),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added event setup"],
                modulepr["added event setup"],
                moduleres["added event setup diff"],
            ),
            '<td align="right"> %0.2f</td><td align="right"> %0.2f</td><td align="right"> %0.2f</td>'
            % (
                moduleib["added total"],
                modulepr["added total"],
                moduleres["added total diff"],
            ),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (
                moduleib["nAlloc construction"],
                modulepr["nAlloc construction"],
                moduleres["nAlloc construction diff"],
            ),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (
                moduleib["nAlloc global begin run"] + moduleib["nAlloc stream begin run"],
                modulepr["nAlloc global begin run"] + modulepr["nAlloc stream begin run"],
                moduleres["nAlloc global begin run diff"]
                + moduleres["nAlloc stream begin run diff"],
            ),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (
                moduleib["nAlloc global begin luminosity block"]
                + moduleib["nAlloc stream begin luminosity block"],
                modulepr["nAlloc global begin luminosity block"]
                + modulepr["nAlloc stream begin luminosity block"],
                moduleres["nAlloc global begin luminosity block diff"]
                + moduleres["nAlloc stream begin luminosity block diff"],
            ),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (moduleib["nAlloc event"], modulepr["nAlloc event"], moduleres["nAlloc event diff"]),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (
                moduleib["nAlloc event setup"],
                modulepr["nAlloc event setup"],
                moduleres["nAlloc event setup diff"],
            ),
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
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
            '<td align="right"> %i</td><td align="right"> %i</td><td align="right"> %i</td>'
            % (moduleib["transitions"], modulepr["transitions"], modulepr["transitions"]-moduleib["transitions"]),
            "</tr>",
        ]

summaryLines += []
summaryLines += ["</body></html>"]

summaryFile = os.path.dirname(sys.argv[2]) + "./diff-" + os.path.basename(sys.argv[2]) + ".html"
with open(summaryFile, "w") as g:
    for summaryLine in summaryLines:
        print(summaryLine, file=g)

