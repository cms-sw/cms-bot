#! /usr/bin/env python3

import sys
import json
import os


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


def sum_numeric_values(data, keys, default="N/A"):
    values = [data.get(key, default) for key in keys]
    return sum(values) if all(isinstance(value, (int, float)) for value in values) else default


def sum_with_prefix_suffix(data, metric_keys, prefix="added", suffix="", default="N/A"):
    return sum_numeric_values(
        data, ["%s %s %s" % (prefix, metric, suffix) for metric in metric_keys], default
    )


def is_valid_module_key(key):
    return key != "None|None|None" and key != "||"




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

update_added_totals(datamapres)

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
