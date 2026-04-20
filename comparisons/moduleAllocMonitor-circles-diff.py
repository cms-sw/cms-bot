#! /usr/bin/env python3

import sys
import json
import os
import html


def build_viewer_html(template_path, embedded_data, source_label):
        with open(template_path, encoding="utf-8") as template_file:
                content = template_file.read()

        embedded_json = json.dumps(embedded_data).replace("</", "<\\/")

        autoload_snippet = """
    <script>
        (function () {
            var embeddedData = %s;
            if (typeof loadFromObject === "function") {
                loadFromObject(embeddedData, %s);
            }
        })();
    </script>
""" % (embedded_json, json.dumps(source_label))

        if "</body>" in content:
                content = content.replace("</body>", autoload_snippet + "</body>", 1)
        return content

threshold = 5000.0
error_threshold = 20000.0

BEGIN_JOB_KEYS = ["begin job"]
BEGIN_RUN_KEYS = ["global begin run", "stream begin run"]
BEGIN_LUMI_KEYS = [
    "global begin luminosity block",
    "stream begin luminosity block",
]
CONSTRUCTION_KEYS = ["construction"]
EVENT_KEYS = ["event"]
EVENT_SETUP_KEYS = ["event setup"]
TOTAL_KEYS = [
    *CONSTRUCTION_KEYS,
    *BEGIN_RUN_KEYS,
    *BEGIN_LUMI_KEYS,
    *EVENT_KEYS,
    *EVENT_SETUP_KEYS,
]

METRICS_KEYS = ["added", "nAlloc", "nDealloc", "maxTemp", "max1Alloc"]


def module_key(module):
    return "%s|%s|%s" % (module.get("label", ""), module.get("type", ""), module.get("record", ""))


def numeric_value(data, key, default="N/A"):
    value = data.get(key, default)
    return value if isinstance(value, (int, float)) else default


def sum_numeric_values(data, keys, default="N/A"):
    values = [data.get(key, default) for key in keys]
    return sum(values) if all(isinstance(value, (int, float)) for value in values) else default


def sum_with_prefix_suffix(data, metric_keys, prefix="added", suffix="", default="N/A"):
    return sum_numeric_values(
        data, ["%s %s %s" % (prefix, metric, suffix) for metric in metric_keys], default
    )


def format_metric(value):
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def safe_text(value, default=""):
    text = default if value is None else str(value)
    return html.escape(text, quote=True)


def append_triplet_cell(summary_lines, ib, pr, diff, attrs=''):
    summary_lines.extend([
        "<td %s>%s</td>" % (attrs, safe_text(format_metric(ib))),
        "<td %s>%s</td>" % (attrs, safe_text(format_metric(pr))),
        "<td %s>%s</td>" % (attrs, safe_text(format_metric(diff))),
    ])


def added_total_color(diff_value):
    if not isinstance(diff_value, (int, float)):
        return ""
    if diff_value > error_threshold:
        return "red"
    if diff_value > threshold:
        return "orange"
    if diff_value < -1.0 * error_threshold:
        return "green"
    if diff_value < -1.0 * threshold:
        return "cyan"
    return ""


def is_valid_module_key(key):
    return key != "None|None|None" and key != "||"


def transitions_diff_value(transitions_ib, transitions_pr):
    if isinstance(transitions_ib, (int, float)) and isinstance(transitions_pr, (int, float)):
        return transitions_ib - transitions_pr
    if not isinstance(transitions_ib, (int, float)) and isinstance(transitions_pr, (int, float)):
        return transitions_pr - 0
    if isinstance(transitions_ib, (int, float)) and not isinstance(transitions_pr, (int, float)):
        return 0 - transitions_ib
    return "N/A"


def update_added_totals(datamapres):
    for module in datamapres.values():
        key = module_key(module)
        if not is_valid_module_key(key):
            continue
        for metric in METRICS_KEYS:
            module[f"{metric} total PR"] = sum_with_prefix_suffix(
                module, TOTAL_KEYS, prefix=metric, suffix="PR"
            )
            module[f"{metric} total IB"] = sum_with_prefix_suffix(
                module, TOTAL_KEYS, prefix=metric, suffix="IB"
            )
            module[f"{metric} total diff"] = sum_with_prefix_suffix(
                module, TOTAL_KEYS, prefix=metric, suffix="diff"
            )


def build_header_row():
    return [
        '<th >added begin job IB</th>',
        '<th >added begin job PR</th>',
        '<th >added begin job diff</th>',
        '<th >added construction IB</th>',
        '<th >added construction PR</th>',
        '<th >added construction diff</th>',
        '<th >added begin run IB</th>',
        '<th >added begin run PR</th>',
        '<th >added begin run diff</th>',
        '<th >added begin luminosity block IB</th>',
        '<th >added begin luminosity block PR</th>',
        '<th >added begin luminosity block diff</th>',
        '<th >added event IB</th>',
        '<th >added event PR</th>',
        '<th >added event diff</th>',
        '<th >added event setup IB</th>',
        '<th >added event setup PR</th>',
        '<th >added event setup diff</th>',
        '<th >added total IB</th>',
        '<th >added total PR</th>',
        '<th >added total diff</th>',
        '<th >nAlloc begin job IB</th>',
        '<th >nAlloc begin job PR</th>',
        '<th >nAlloc begin job diff</th>',
        '<th >nAlloc construction IB</th>',
        '<th >nAlloc construction PR</th>',
        '<th >nAlloc construction diff</th>',
        '<th >nAlloc begin run IB</th>',
        '<th >nDealloc begin run PR</th>',
        '<th >nDealloc begin run diff</th>',
        '<th >nDealloc begin luminosity block IB</th>',
        '<th >nDealloc begin luminosity block PR</th>',
        '<th >nDealloc begin luminosity block diff</th>',
        '<th >nDealloc event IB</th>',
        '<th >nDealloc event PR</th>',
        '<th >nDealloc event diff</th>',
        '<th >nDealloc event setup IB</th>',
        '<th >nDealloc event setup PR</th>',
        '<th >nDealloc event setup diff</th>',
        '<th >nDealloc total IB</th>',
        '<th >nDealloc total PR</th>',
        '<th >nDealloc total diff</th>',
        '<th >nDealloc begin job IB</th>',
        '<th >nDealloc begin job PR</th>',
        '<th >nDealloc begin job diff</th>',
        '<th >nDealloc construction IB</th>',
        '<th >nDealloc construction PR</th>',
        '<th >nDealloc construction diff</th>',
        '<th >nDealloc begin run IB</th>',
        '<th >nDealloc begin run PR</th>',
        '<th >nDealloc begin run diff</th>',
        '<th >nDealloc begin luminosity block IB</th>',
        '<th >nDealloc begin luminosity block PR</th>',
        '<th >nDealloc begin luminosity block diff</th>',
        '<th >nDealloc event IB</th>',
        '<th >nDealloc event PR</th>',
        '<th >nDealloc event diff</th>',
        '<th >nDealloc event setup IB</th>',
        '<th >nDealloc event setup PR</th>',
        '<th >nDealloc event setup diff</th>',
        '<th >nDealloc total IB</th>',
        '<th >nDealloc total PR</th>',
        '<th >nDealloc total diff</th>',
        '<th >maxTemp begin job IB</th>',
        '<th >maxTemp begin job PR</th>',
        '<th >maxTemp begin job diff</th>',
        '<th >maxTemp construction IB</th>',
        '<th >maxTemp construction PR</th>',
        '<th >maxTemp construction diff</th>',
        '<th >maxTemp begin run IB</th>',
        '<th >maxTemp begin run PR</th>',
        '<th >maxTemp begin run diff</th>',
        '<th >maxTemp begin luminosity block IB</th>',
        '<th >maxTemp begin luminosity block PR</th>',
        '<th >maxTemp begin luminosity block diff</th>',
        '<th >maxTemp event IB</th>',
        '<th >maxTemp event PR</th>',
        '<th >maxTemp event diff</th>',
        '<th >maxTemp event setup IB</th>',
        '<th >maxTemp event setup PR</th>',
        '<th >maxTemp event setup diff</th>',
        '<th >maxTemp total IB</th>',
        '<th >maxTemp total PR</th>',
        '<th >maxTemp total diff</th>',
        '<th >max1Alloc begin job IB</th>',
        '<th >max1Alloc begin job PR</th>',
        '<th >max1Alloc begin job diff</th>',
        '<th >max1Alloc construction IB</th>',
        '<th >max1Alloc construction PR</th>',
        '<th >max1Alloc construction diff</th>',
        '<th >max1Alloc begin run IB</th>',
        '<th >max1Alloc begin run PR</th>',
        '<th >max1Alloc begin run diff</th>',
        '<th >max1Alloc begin luminosity block IB</th>',
        '<th >max1Alloc begin luminosity block PR</th>',
        '<th >max1Alloc begin luminosity block diff</th>',
        '<th >max1Alloc event IB</th>',
        '<th >max1Alloc event PR</th>',
        '<th >max1Alloc event diff</th>',
        '<th >max1Alloc event setup IB</th>',
        '<th >max1Alloc event setup PR</th>',
        '<th >max1Alloc event setup diff</th>',
        '<th >max1Alloc total IB</th>',
        '<th >max1Alloc total PR</th>',
        '<th >max1Alloc total diff</th>',
    ]


def build_summary_header(ibdata, prdata, results):
    summary_header = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<title>ModuleAllocMonitor Resources Difference</title>",
    ]
    summary_header += [
        "<style>",
        "table, th, td {border: 1px solid black;}</style>",
        "<style> th, td {padding: 15px;}</style></head>",
        "<body><h3>ModuleAllocMonitor Resources Difference</h3>",
        '<table id="thresholds"><tr><td style="background-color: orange;">',
        "warn threshold %0.2f kB" % threshold,
        '</td></tr><tr><td style="background-color: red;">',
        "error threshold %0.2f kB" % error_threshold,
        '</td></tr><tr><td style="background-color: green;">',
        "warn threshold -%0.2f kB" % threshold,
        '</td></tr><tr><td style="background-color: cyan;">',
        "warn threshold -%0.2f kB" % error_threshold,
        "</td></tr>",
        "<tr><td>metric:<BR>&lt;baseline&gt;<BR>&lt;pull request&gt;<BR>&lt;PR - baseline&gt; </td>",
        "</tr></table>",
        '<table id="summary">',
        '<thead><tr><th >Type</th><th >Label</th><th >Record</th>',
    ]
    summary_header += build_header_row()
    summary_header += [
        "</tr>",
        "</thead>",
        "<tbody>",
        "<tr>",
        "<td>%s</td><td>%s</td><td>%s</td>"
        % (
            safe_text(prdata["total"]["type"]),
            safe_text(prdata["total"]["label"]),
            safe_text(prdata["total"].get("record", "N/A")),
        ),
    ]
    for metric in METRICS_KEYS:
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in BEGIN_JOB_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in BEGIN_JOB_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in BEGIN_JOB_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in CONSTRUCTION_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in CONSTRUCTION_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in CONSTRUCTION_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in BEGIN_RUN_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in BEGIN_RUN_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in BEGIN_RUN_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in BEGIN_LUMI_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in BEGIN_LUMI_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in BEGIN_LUMI_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in EVENT_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in EVENT_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in EVENT_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in EVENT_SETUP_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in EVENT_SETUP_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in EVENT_SETUP_KEYS]
            ),
        )
        append_triplet_cell(
            summary_header,
            sum_numeric_values(
                results["total"], ["%s %s IB" % (metric, key) for key in TOTAL_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s PR" % (metric, key) for key in TOTAL_KEYS]
            ),
            sum_numeric_values(
                results["total"], ["%s %s diff" % (metric, key) for key in TOTAL_KEYS]
            ),
        )
    summary_header += [
        "</tr></tbody></table>",
        '<table id="module_summary">',
        "<thead>",
        '<tr><th >Module label</th>',
        '<th >Module type</th>',
        '<th >Module record</th>',
    ]
    summary_header += build_header_row()
    summary_header += [
        '<th >transitions IB</th>',
        '<th >transitions PR</th>',
        '<th >transitions diff</th>',
        "</tr>",
    ]
    return summary_header


def append_module_columns_prefix(summary_lines, moduleres, prefix):
    cell_style = "text-align: right;"
    if prefix == "added":
        addedtotaldiff = numeric_value(moduleres, "added total diff", float("-inf"))
        color = added_total_color(addedtotaldiff)
        if color:
            cell_style += f" background-color: {color};"
    cell_attrs = f'style="{cell_style}"'
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, BEGIN_JOB_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, BEGIN_JOB_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, BEGIN_JOB_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, CONSTRUCTION_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, CONSTRUCTION_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, CONSTRUCTION_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, BEGIN_RUN_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, BEGIN_RUN_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, BEGIN_RUN_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, BEGIN_LUMI_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, BEGIN_LUMI_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, BEGIN_LUMI_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, EVENT_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, EVENT_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, EVENT_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, EVENT_SETUP_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, EVENT_SETUP_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, EVENT_SETUP_KEYS, prefix=prefix, suffix="diff"),
    )
    append_triplet_cell(
        summary_lines,
        sum_with_prefix_suffix(moduleres, TOTAL_KEYS, prefix=prefix, suffix="IB"),
        sum_with_prefix_suffix(moduleres, TOTAL_KEYS, prefix=prefix, suffix="PR"),
        sum_with_prefix_suffix(moduleres, TOTAL_KEYS, prefix=prefix, suffix="diff"),
        attrs=cell_attrs,
    )


def append_module_rows(summary_lines, moduleib, modulepr, moduleres):
    summary_lines += [
        "<tr>",
        '<td>%s</td><td>%s</td><td>%s</td>'
        % (
            safe_text(moduleres.get("label", "")),
            safe_text(moduleres.get("type", "")),
            safe_text(moduleres.get("record", "N/A")),
        ),
    ]
    for metric in METRICS_KEYS:
        append_module_columns_prefix(summary_lines, moduleres, metric)
    transitions_ib = numeric_value(moduleib, "transitions")
    transitions_pr = numeric_value(modulepr, "transitions")
    transitions_diff = transitions_diff_value(transitions_ib, transitions_pr)
    append_triplet_cell(summary_lines, transitions_ib, transitions_pr, transitions_diff)
    summary_lines += ["</tr>"]


def append_sorted_module_rows(summary_lines, datamapib, datamappr, datamapres):
    for item in sorted(
        datamapres.items(),
        key=lambda x: numeric_value(x[1], "added total diff", float("-inf")),
        reverse=True,
    ):
        key = module_key(item[1])
        if not is_valid_module_key(key):
            continue
        moduleib = datamapib.get(key, {})
        modulepr = datamappr.get(key, {})
        moduleres = datamapres.get(key, {})
        append_module_rows(summary_lines, moduleib, modulepr, moduleres)


def build_summary_lines(ibdata, prdata, results, datamapib, datamappr, datamapres):
    summary_lines = build_summary_header(ibdata, prdata, results)
    update_added_totals(datamapres)
    append_sorted_module_rows(summary_lines, datamapib, datamappr, datamapres)
    summary_lines += [
        "</table>"]
    summary_lines += [
        "</body></html>",
    ]
    return summary_lines


def diff_from(metrics, data, dest, res):
    for metric in metrics:
        ibkey = "%s IB" % metric
        res[ibkey] = data.get(metric, "N/A")
        prkey = "%s PR" % metric
        res[prkey] = dest.get(metric, "N/A")
        if res[ibkey] == "N/A" or res[prkey] == "N/A":
            if res[prkey] != "N/A":
                res[metric + " diff"] = res[prkey] - 0
            elif res[ibkey] != "N/A":
                res[metric + " diff"] = 0 - res[ibkey]
        else:
            dmetric = dest.get(metric) - data.get(metric)
            res[metric + " diff"] = dmetric


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

datamapib = {module_key(module): module for module in ibdata["modules"]}

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

datamappr = {module_key(module): module for module in prdata["modules"]}


if ibdata["total"]["label"] != prdata["total"]["label"]:
    print("Warning: input files describe different process names")

results = {}
results["resources"] = []
for resource in prdata["resources"]:
    resourcediff = resource.copy()
    resourceib = resource.copy()
    resourcepr = resource.copy()
    for k, v in resource.items():
        resourcediff[k] = "%s diff" % v
        resourceib[k] = "%s IB" % v
        resourcepr[k] = "%s PR" % v
    results["resources"].append(resourcediff)
    results["resources"].append(resourceib)
    results["resources"].append(resourcepr)

results["total"] = {}
results["total"]["type"] = prdata["total"]["type"]
results["total"]["label"] = prdata["total"]["label"]

diff_from(metrics, ibdata["total"], prdata["total"], results["total"])

results["modules"] = []
keys = set()
for module in prdata["modules"]:
    keys.add(module_key(module))
for module in ibdata["modules"]:
    keys.add(module_key(module))
for key in sorted(keys):
    result = {}
    if key in datamapib and key not in datamappr:
        result["type"] = datamapib.get(key).get("type")
        result["label"] = datamapib.get(key).get("label")
        result["record"] = datamapib.get(key).get("record")
        diff_from(metrics, datamapib.get(key, {}), {}, result)
    elif key in datamappr and key not in datamapib:
        result["type"] = datamappr.get(key).get("type")
        result["label"] = datamappr.get(key).get("label")
        result["record"] = datamappr.get(key).get("record")
        diff_from(metrics, {}, datamappr.get(key, {}), result)
    else:
        result["type"] = datamappr.get(key).get("type")
        result["label"] = datamappr.get(key).get("label")
        result["record"] = datamappr.get(key).get("record")
        diff_from(metrics, datamapib.get(key, {}), datamappr.get(key, {}), result)
    results["modules"].append(result)

datamapres = {}
for module in results["modules"]:
    datamapres[module_key(module)] = module
dumpfile = (
    os.path.dirname(os.path.realpath(sys.argv[2]))
    + "/diff-"
    + os.path.basename(os.path.realpath(sys.argv[2]))
)
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)

summaryFile = (
    os.path.dirname(os.path.realpath(sys.argv[2]))
    + "/diff-"
    + os.path.basename(os.path.realpath(sys.argv[2]))
    + ".html"
)

templateFile = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "module_alloc_monitor_viewer.html"
)
summaryHtml = build_viewer_html(template_path=templateFile, embedded_data=results, source_label="embedded diff data")

with open(summaryFile, "w", encoding="utf-8") as g:
    g.write(summaryHtml)
