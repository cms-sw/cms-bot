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

selectable_metrics = {
    "added_total": "Sum All (kB)",
    "added_construction": "Construction (kB)",
    "added_begin_run": "Begin Run (kB)",
    "added_begin_lumi": "Begin Luminosity Block (kB)",
    "added_event": "Event (kB)",
    "added_event_setup": "Event Setup (kB)",
    "nalloc_construction": "nAlloc Construction",
    "nalloc_begin_run": "nAlloc Begin Run",
    "nalloc_begin_lumi": "nAlloc Begin Luminosity Block",
    "nalloc_event": "nAlloc Event",
    "nalloc_event_setup": "nAlloc Event Setup",
    "nalloc_total": "nAlloc Sum All",
    "transitions": "transitions",
}

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
    "    var rows = Array.prototype.slice.call(table.rows, 2);",
    '    var previousColumn = parseInt(table.getAttribute("data-sort-column"), 10);',
    '    var previousDirection = table.getAttribute("data-sort-direction") || "desc";',
    '    var direction = "desc";',
    "    if (!isNaN(previousColumn) && previousColumn === colIndex) {",
    '        direction = previousDirection === "desc" ? "asc" : "desc";',
    "    }",
    "",
    "    rows.sort(function(a, b) {",
    '        var xCell = a.getElementsByTagName("td")[colIndex];',
    '        var yCell = b.getElementsByTagName("td")[colIndex];',
    '        var xText = xCell ? xCell.textContent.trim() : "";',
    '        var yText = yCell ? yCell.textContent.trim() : "";',
    "",
    "        var xNum = Number(xText);",
    "        var yNum = Number(yText);",
    '        var xIsNum = xText !== "" && !isNaN(xNum);',
    '        var yIsNum = yText !== "" && !isNaN(yNum);',
    "",
    "        var cmp = 0;",
    "        if (xIsNum && yIsNum) {",
    "            cmp = xNum - yNum;",
    "        } else {",
    "            cmp = xText.localeCompare(yText);",
    "        }",
    '        return direction === "asc" ? cmp : -cmp;',
    "    });",
    "",
    "    for (var i = 0; i < rows.length; i++) {",
    "        table.appendChild(rows[i]);",
    "    }",
    "",
    '    table.setAttribute("data-sort-column", colIndex);',
    '    table.setAttribute("data-sort-direction", direction);',
    "}",
    "function updateMetricColumn(sortAfterUpdate) {",
    '    var selector = document.getElementById("metricSelector");',
    "    if (!selector) return;",
    "    var selectedMetric = selector.value;",
    '    var selectedMetricLabel = document.getElementById("selectedMetricLabel");',
    "    if (selectedMetricLabel) {",
    "        var opt = selector.options[selector.selectedIndex];",
    "        selectedMetricLabel.textContent = opt ? opt.text : selectedMetric;",
    "    }",
    '    var cells = document.getElementsByClassName("selectedMetric");',
    "    for (var i = 0; i < cells.length; i++) {",
    '        var metrics_ib = JSON.parse(cells[i].getAttribute("data-metrics-ib") || "{}");',
    '        var metrics_pr = JSON.parse(cells[i].getAttribute("data-metrics-pr") || "{}");',
    '        var metrics_diffs = JSON.parse(cells[i].getAttribute("data-metrics-diffs") || "{}");',
    '        cells[i].innerHTML = metrics_diffs[selectedMetric] || "";',
    '        cells[i].removeAttribute("bgcolor");',
    "        var diffValue = Number(metrics_diffs[selectedMetric]);",
    "        if (!isNaN(diffValue)) {",
    "            if (diffValue > %s) {" % js_error_threshold,
    '                cells[i].setAttribute("bgcolor", "red");',
    "            } else if (diffValue > %s) {" % js_threshold,
    '                cells[i].setAttribute("bgcolor", "orange");',
    "            } else if (diffValue < -1.0 * %s) {" % js_error_threshold,
    '                cells[i].setAttribute("bgcolor", "green");',
    "            } else if (diffValue < -1.0 * %s) {" % js_threshold,
    '                cells[i].setAttribute("bgcolor", "cyan");',
    "            }",
    "        }",
    "    }",
    "    if (sortAfterUpdate) {",
    '        var table = document.getElementById("moduleTable");',
    "        if (table) {",
    '            table.removeAttribute("data-sort-column");',
    '            table.setAttribute("data-sort-direction", "desc");',
    "            sortTable(table, 4);",
    "        }",
    "    }",
    "}",
    "var hideZeroMetrics = false;",
    "function toggleZeroFilter() {",
    "    hideZeroMetrics = !hideZeroMetrics;",
    '    var btn = document.getElementById("filterZerosBtn");',
    "    if (btn) {",
    '        btn.textContent = hideZeroMetrics ? "Show All" : "Hide Zeros";',
    '        btn.style.backgroundColor = hideZeroMetrics ? "#ffcc00" : "#cccccc";',
    "    }",
    "    filterTable();",
    "}",
    "function filterTable() {",
    '    var searchInput = document.getElementById("moduleSearch");',
    "    if (!searchInput) return;",
    "    var searchText = searchInput.value.toLowerCase();",
    '    var table = document.getElementById("moduleTable");',
    "    if (!table) return;",
    '    var rows = table.getElementsByTagName("tr");',
    "    for (var i = 1; i < rows.length; i++) {",
    '        var cells = rows[i].getElementsByTagName("td");',
    "        if (cells.length >= 4) {",
    "            var label = cells[0].textContent.toLowerCase();",
    "            var type = cells[1].textContent.toLowerCase();",
    "            var record = cells[2].textContent.toLowerCase();",
    "            var metricText = cells[3].textContent.trim();",
    "            var metricValue = parseFloat(metricText);",
    "            var matchesSearch = label.includes(searchText) || type.includes(searchText) || record.includes(searchText);",
    '            var isZero = hideZeroMetrics && (metricValue === 0 || metricText === "");',
    "            if (matchesSearch && !isZero) {",
    '                rows[i].style.display = "";',
    "            } else {",
    '                rows[i].style.display = "none";',
    "            }",
    "        }",
    "    }",
    "}",
    'document.addEventListener("DOMContentLoaded", function() { updateMetricColumn(false); });',
    "</script>",
    "</head>",
    "<body><h3>ModuleAllocMonitor Resources Difference</h3><table></table>",
    "<table>",
    '<tr><td align="center">Type<BR>Label</td>',
    "<td>metric:</td>",
    '<td align="center">added construction</td>',
    '<td align="center">added begin run</td>',
    '<td align="center">added begin luminosity block</td>',
    '<td align="center">added event</td>',
    '<td align="center">added event setup</td>',
    '<td align="center">added total</td>',
    '<td align="center">nAlloc construction</td>',
    '<td align="center">nAlloc begin run</td>',
    '<td align="center">nAlloc begin luminosity block</td>',
    '<td align="center">nAlloc event</td>',
    '<td align="center">nAlloc event setup</td>',
    '<td align="center">nAlloc total</td>',
    "</tr>",
    "<td>%s<BR>%s</td>" % (prdata["total"]["type"], prdata["total"]["label"]),
    '<td align="center">&lt;baseline&gt;<BR>&lt;pull request&gt;<BR>&lt;PR - baseline&gt; </td>',
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
    '<td align="right">%0.2f<br>%0.2f<br>%0.2f</td>'
    % (
        ibdata["total"]["added construction"]
        + ibdata["total"]["added global begin run"]
        + ibdata["total"]["added stream begin run"]
        + ibdata["total"]["added stream begin luminosity block"]
        + ibdata["total"]["added global begin luminosity block"]
        + ibdata["total"]["added event"]
        + ibdata["total"]["added event setup"],
        prdata["total"]["added construction"]
        + prdata["total"]["added global begin run"]
        + prdata["total"]["added stream begin run"]
        + prdata["total"]["added stream begin luminosity block"]
        + prdata["total"]["added global begin luminosity block"]
        + prdata["total"]["added event"]
        + prdata["total"]["added event setup"],
        results["total"]["added construction diff"]
        + results["total"]["added global begin run diff"]
        + results["total"]["added stream begin run diff"]
        + results["total"]["added stream begin luminosity block diff"]
        + results["total"]["added global begin luminosity block diff"]
        + results["total"]["added event diff"]
        + results["total"]["added event setup diff"],
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
    '<td align="right">%0.f<br>%0.f<br>%0.f</td>'
    % (
        ibdata["total"]["nAlloc event setup"]
        + ibdata["total"]["nAlloc event"]
        + ibdata["total"]["nAlloc construction"]
        + ibdata["total"]["nAlloc global begin run"]
        + ibdata["total"]["nAlloc stream begin run"]
        + ibdata["total"]["nAlloc global begin luminosity block"]
        + ibdata["total"]["nAlloc stream begin luminosity block"],
        prdata["total"]["nAlloc event setup"]
        + prdata["total"]["nAlloc event"]
        + prdata["total"]["nAlloc construction"]
        + prdata["total"]["nAlloc global begin run"]
        + prdata["total"]["nAlloc stream begin run"]
        + prdata["total"]["nAlloc global begin luminosity block"]
        + prdata["total"]["nAlloc stream begin luminosity block"],
        results["total"]["nAlloc event setup diff"]
        + results["total"]["nAlloc event diff"]
        + results["total"]["nAlloc construction diff"]
        + results["total"]["nAlloc global begin run diff"]
        + results["total"]["nAlloc stream begin run diff"]
        + results["total"]["nAlloc global begin luminosity block diff"]
        + results["total"]["nAlloc stream begin luminosity block diff"],
    ),
    "</tr></table>",
    '<table><tr><td bgcolor="orange">',
    "warn threshold %0.2f kB" % threshold,
    '</td></tr><tr><td bgcolor="red">',
    "error threshold %0.2f kB" % error_threshold,
    '</td></tr><tr><td bgcolor="green">',
    "warn threshold -%0.2f kB" % threshold,
    '</td></tr><tr><td bgcolor="cyan">',
    "warn threshold -%0.2f kB" % error_threshold,
    "</td></tr>",
    "</table>",
    '<table id="moduleTable">',
    "<tr>",
    '<th align="center" colspan="3">Search<BR><input type="text" id="moduleSearch" placeholder="label/type/record" onkeyup="filterTable()" style="width:130px"></th>',
    '<th align="left" colspan="3"><button id="filterZerosBtn" onclick="toggleZeroFilter()" style="margin-top:5px;padding:4px 8px;background-color:#cccccc;border:1px solid #999;border-radius:3px;cursor:pointer;font-size:12px">Hide Zeros</button></th>'
    "</tr>",
    "<tr>",
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 1)">Module label</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 2)">Module type</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 3)">Module transition</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 4)">Metric IB:</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 4)">Metric PR:</th>',
    '<th align="center" onclick="sortTable(document.getElementById(\'moduleTable\'), 4)">Metric PR-IB:</th>',
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

dumpfile = (
    os.path.dirname(os.path.realpath(sys.argv[2]))
    + "/diff-"
    + os.path.basename(os.path.realpath(sys.argv[2]))
    + ".json"
)
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
        selected_metric_values_ib = {
            "added_total": "%0.2f" % moduleib["added total"],
            "added_construction": "%0.2f" % moduleib["added construction"],
            "added_begin_run": "%0.2f"
            % (moduleib["added global begin run"] + moduleib["added stream begin run"]),
             "added_begin_lumi": "%0.2f"
            % (
                moduleib["added global begin luminosity block"]
                + moduleib["added stream begin luminosity block"]
            ),
            "added_event": "%0.2f" % moduleib["added event"],
            "added_event_setup": "%0.2f" % moduleib["added event setup"],
            "nalloc_construction": "%i" % moduleib["nAlloc construction"],
            "nalloc_begin_run": "%i"
            % (modulepr["nAlloc global begin run"] + modulepr["nAlloc stream begin run"]),
            "nalloc_begin_lumi": "%i"
            % (
                moduleib["nAlloc global begin luminosity block"]
                + moduleib["nAlloc stream begin luminosity block"]
            ),
            "nalloc_event": "%i" % moduleib["nAlloc event"],
            "nalloc_event_setup": "%i" % moduleib["nAlloc event setup"],
            "nalloc_total": "%i"
            % (
                moduleib["nAlloc event setup"]
                + moduleib["nAlloc event"]
                + moduleib["nAlloc construction"]
            ),
            "transitions": "%i" % moduleib["transitions"],
        }
        selected_metric_values_pr = {
            "added_total": "%0.2f" % modulepr["added total"],
            "added_construction": "%0.2f" % modulepr["added construction"],
            "added_begin_run": "%0.2f"
            % (modulepr["added global begin run"] + modulepr["added stream begin run"]),
            "added_begin_lumi": "%0.2f"
            % (
                modulepr["added global begin luminosity block"]
                + modulepr["added stream begin luminosity block"]
            ),
            "added_event": "%0.2f" % modulepr["added event"],
            "added_event_setup": "%0.2f" % modulepr["added event setup"],
            "nalloc_construction": "%i" % modulepr["nAlloc construction"],
            "nalloc_begin_run": "%i"
            % (modulepr["nAlloc global begin run"] + modulepr["nAlloc stream begin run"]),
            "nalloc_begin_lumi": "%i"
            % (
                modulepr["nAlloc global begin luminosity block"]
                + modulepr["nAlloc stream begin luminosity block"]
            ),
            "nalloc_event": "%i" % modulepr["nAlloc event"],
            "nalloc_event_setup": "%i" % modulepr["nAlloc event setup"],
            "nalloc_total": "%i"
            % (
                modulepr["nAlloc event setup"]
                + modulepr["nAlloc event"]
                + modulepr["nAlloc construction"]
            ),
            "transitions": "%i" % modulepr["transitions"],
        }
        selected_metric_values_diffs = {
            "added_construction": moduleres["added construction diff"],
            "added_begin_run": moduleres["added global begin run diff"]
            + moduleres["added stream begin run diff"],
            "added_begin_lumi": moduleres["added global begin luminosity block diff"]
            + moduleres["added stream begin luminosity block diff"],
            "added_event": moduleres["added event diff"],
            "added_event_setup": moduleres["added event setup diff"],
            "added_total": moduleres["added total diff"],
            "nalloc_construction": moduleres["nAlloc construction diff"],
            "nalloc_begin_run": moduleres["nAlloc global begin run diff"]
            + moduleres["nAlloc stream begin run diff"],
            "nalloc_begin_lumi": moduleres["nAlloc global begin luminosity block diff"]
            + moduleres["nAlloc stream begin luminosity block diff"],
            "nalloc_event": moduleres["nAlloc event diff"],
            "nalloc_event_setup": moduleres["nAlloc event setup diff"],
            "nalloc_total": moduleres["nAlloc event setup diff"]
            + moduleres["nAlloc event diff"]
            + moduleres["nAlloc construction diff"],
            "transitions": modulepr["transitions"] - moduleib["transitions"],
        }
        selected_metric_ib_json = json.dumps(selected_metric_values_ib).replace("'", "&apos;")
        selected_metric_pr_json = json.dumps(selected_metric_values_pr).replace("'", "&apos;")
        selected_metric_diffs_json = json.dumps(selected_metric_values_diffs).replace("'", "&apos;")
        record_value = moduleres.get("record")
        if record_value:

            for selected_metric in ["added_total", "added_construction"]:
                summaryLines += [
                    "<tr>",
                '<td align="left">%s</td><td align="left">%s</td><td align="left">%s</td>'
                % (moduleres["label"], moduleres["type"], selectable_metrics[selected_metric]),
                '<td align="right">%s</td><td align="right">%s</td><td align="right">%s</td>' %
                (
                    selected_metric_values_ib[selected_metric],
                    selected_metric_values_pr[selected_metric],
                    selected_metric_values_diffs[selected_metric],
                ),
                    "</tr>",
                    ]
            summaryLines += [
                "<tr>",
                '<td align="left">%s</td><td align="left">%s</td><td align="left">Record: %s</td>'
                % (moduleres["label"], moduleres["type"], record_value),
                "<td align=\"right\">%s</td><td align=\"right\">%s</td><td align=\"right\">%s</td>"
                % (selected_metric_values_ib["added_event_setup"], selected_metric_values_pr["added_event_setup"], selected_metric_values_diffs["added_event_setup"]),
                "</tr>",
            ]
        else:
            for selected_metric in ["added_total", "added_construction", "added_begin_run", "added_begin_lumi", "added_event",]    :
                summaryLines += [
                    "<tr>",
                '<td align="left">%s</td><td align="left">%s</td><td align="left">%s</td>'
                % (moduleres["label"], moduleres["type"], selectable_metrics[selected_metric]),
                '<td align="right">%s</td><td align="right">%s</td><td align="right">%s</td>' %
                (
                    selected_metric_values_ib[selected_metric],
                    selected_metric_values_pr[selected_metric],
                    selected_metric_values_diffs[selected_metric],
                ),
                "</tr>",
            ]

summaryLines += []
summaryLines += ["</body></html>"]

summaryFile = (
    os.path.dirname(os.path.realpath(sys.argv[2]))
    + "/diff-"
    + os.path.basename(os.path.realpath(sys.argv[2]))
    + ".html"
)
with open(summaryFile, "w") as g:
    for summaryLine in summaryLines:
        print(summaryLine, file=g)
