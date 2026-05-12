#! /usr/bin/env python3

import sys
import json
import os

VIEWER_TEMPLATE = "resources_diff_viewer.html"


def build_viewer_html(template_path, embedded_data, source_label):
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()

    embedded_json = json.dumps(embedded_data).replace("</", "<\\/")

    autoload_snippet = """
    <script id="embedded-resources-diff-data" type="application/json">%s</script>
    <script>
        (function () {
            var dataNode = document.getElementById("embedded-resources-diff-data");
            if (!dataNode) {
                return;
            }
            var embeddedData = JSON.parse(dataNode.textContent);
            if (typeof loadFromObject === "function") {
                loadFromObject(embeddedData, %s);
            }
        })();
    </script>
""" % (embedded_json, json.dumps(source_label))

    if "</body>" in content:
        content = content.replace("</body>", autoload_snippet + "</body>", 1)
    return content


def get_or_default(data, key, default=0):
    value = data.get(key, default)
    return value if isinstance(value, (int, float, str)) else default


def build_summary_payload(
    ibdata, prdata, results, datamapib, datamappr, datamapres, threshold, error_threshold
):
    total_ib = ibdata.get("total", {})
    total_pr = prdata.get("total", {})
    total_res = results.get("total", {})

    payload = {
        "title": "FastTimerService Resources Difference",
        "threshold": threshold,
        "errorThreshold": error_threshold,
        "total": {
            "type": total_pr.get("type", ""),
            "label": total_pr.get("label", ""),
            "time_real": {
                "ib": get_or_default(total_ib, "time_real", 0.0),
                "pr": get_or_default(total_pr, "time_real", 0.0),
                "diff": get_or_default(total_res, "time_real_diff", 0.0),
            },
            "time_thread": {
                "ib": get_or_default(total_ib, "time_thread", 0.0),
                "pr": get_or_default(total_pr, "time_thread", 0.0),
                "diff": get_or_default(total_res, "time_thread_diff", 0.0),
            },
            "mem_alloc": {
                "ib": get_or_default(total_ib, "mem_alloc", 0.0),
                "pr": get_or_default(total_pr, "mem_alloc", 0.0),
                "diff": get_or_default(total_res, "mem_alloc_diff", 0.0),
            },
            "mem_free": {
                "ib": get_or_default(total_ib, "mem_free", 0.0),
                "pr": get_or_default(total_pr, "mem_free", 0.0),
                "diff": get_or_default(total_res, "mem_free_diff", 0.0),
            },
            "events": {
                "ib": get_or_default(total_ib, "events", 0),
                "pr": get_or_default(total_pr, "events", 0),
                "diff": get_or_default(total_pr, "events", 0)
                - get_or_default(total_ib, "events", 0),
            },
        },
        "modules": [],
    }

    for item in sorted(
        datamapres.items(), key=lambda x: x[1].get("time_thread_frac_diff", 0), reverse=True
    ):
        module_res = item[1]
        key = module_res.get("type", "") + "|" + module_res.get("label", "")
        if key == "|":
            continue

        module_ib = datamapib.get(key, {})
        module_pr = datamappr.get(key, {})

        payload["modules"].append(
            {
                "type": module_res.get("type", ""),
                "label": module_res.get("label", ""),
                "time_real": {
                    "ib": get_or_default(module_ib, "time_real", 0.0),
                    "pr": get_or_default(module_pr, "time_real", 0.0),
                    "diff": get_or_default(module_res, "time_real_diff", 0.0),
                    "frac_ib": get_or_default(module_ib, "time_real_frac", 0.0),
                    "frac_pr": get_or_default(module_pr, "time_real_frac", 0.0),
                    "frac_diff": get_or_default(module_res, "time_real_frac_diff", 0.0),
                },
                "time_thread": {
                    "ib": get_or_default(module_ib, "time_thread", 0.0),
                    "pr": get_or_default(module_pr, "time_thread", 0.0),
                    "diff": get_or_default(module_res, "time_thread_diff", 0.0),
                    "frac_ib": get_or_default(module_ib, "time_thread_frac", 0.0),
                    "frac_pr": get_or_default(module_pr, "time_thread_frac", 0.0),
                    "frac_diff": get_or_default(module_res, "time_thread_frac_diff", 0.0),
                },
                "mem_alloc": {
                    "ib": get_or_default(module_ib, "mem_alloc", 0.0),
                    "pr": get_or_default(module_pr, "mem_alloc", 0.0),
                    "diff": get_or_default(module_res, "mem_alloc_diff", 0.0),
                },
                "mem_free": {
                    "ib": get_or_default(module_ib, "mem_free", 0.0),
                    "pr": get_or_default(module_pr, "mem_free", 0.0),
                    "diff": get_or_default(module_res, "mem_free_diff", 0.0),
                },
                "events": {
                    "ib": get_or_default(module_ib, "events", 0),
                    "pr": get_or_default(module_pr, "events", 0),
                    "diff": get_or_default(module_pr, "events", 0)
                    - get_or_default(module_ib, "events", 0),
                },
            }
        )

    return payload


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
output_dir = os.path.dirname(os.path.realpath(sys.argv[2]))
output_base = "diff-" + os.path.basename(sys.argv[2])

summaryFile = os.path.join(output_dir, output_base + ".html")

payload = build_summary_payload(
    ibdata=ibdata,
    prdata=prdata,
    results=results,
    datamapib=datamapib,
    datamappr=datamappr,
    datamapres=datamapres,
    threshold=threshold,
    error_threshold=error_threshold,
)

viewer_template = os.path.join(os.path.dirname(os.path.realpath(__file__)), VIEWER_TEMPLATE)
summaryHtml = build_viewer_html(viewer_template, payload, "embedded resources diff")

with open(summaryFile, "w", encoding="utf-8") as g:
    g.write(summaryHtml)

dumpfile = os.path.join(output_dir, output_base)
with open(dumpfile, "w") as f:
    json.dump(results, f, indent=2)
