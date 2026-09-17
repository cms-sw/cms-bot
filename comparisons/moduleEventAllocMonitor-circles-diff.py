#! /usr/bin/env python3

import json
import os
import sys

METRIC_SPECS = [
    ("TotalMemoryGrowth", "bytes"),
    ("AvgRetained", "bytes"),
    ("AvgDataProductSize", "bytes"),
    ("AvgTempSize", "bytes"),
    ("AvgNTemp", "count"),
]


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


def module_key(module):
    return "%s|%s" % (module.get("label", ""), module.get("type", ""))


def diff_value(ib_value, pr_value):
    if isinstance(ib_value, (int, float)) and isinstance(pr_value, (int, float)):
        return pr_value - ib_value
    if isinstance(pr_value, (int, float)):
        return pr_value
    if isinstance(ib_value, (int, float)):
        return -ib_value
    return "N/A"


def diff_from(metric_names, ib_data, pr_data, result):
    for metric in metric_names:
        ib_key = "%s IB" % metric
        pr_key = "%s PR" % metric
        ib_value = ib_data.get(metric, "N/A")
        pr_value = pr_data.get(metric, "N/A")
        result[ib_key] = ib_value
        result[pr_key] = pr_value
        result[metric + " diff"] = diff_value(ib_value, pr_value)


def merge_report(report_map, report, key_hint):
    module = {
        "label": report.get("label", key_hint),
        "type": report.get("type", ""),
    }
    for metric_name, _unit in METRIC_SPECS:
        value = report.get(metric_name, "N/A")
        if isinstance(value, (int, float)):
            module[metric_name] = value

    key = module_key(module)
    existing = report_map.get(key)
    if not existing:
        report_map[key] = module
        return

    for metric_name, _unit in METRIC_SPECS:
        if isinstance(module.get(metric_name), (int, float)):
            existing[metric_name] = existing.get(metric_name, 0) + module[metric_name]


def load_reports(path):
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    memory_reports = data.get("memoryReports")
    if not isinstance(memory_reports, dict):
        raise ValueError('Expected top-level key "memoryReports" in %s' % path)

    modules = {}
    for key_hint, report in memory_reports.items():
        if not isinstance(report, dict):
            continue
        merge_report(modules, report, key_hint)
    return modules


def compute_total(modules, label):
    total = {"type": "Process", "label": label}
    for metric_name, _unit in METRIC_SPECS:
        total[metric_name] = sum(
            module.get(metric_name, 0)
            for module in modules.values()
            if isinstance(module.get(metric_name), (int, float))
        )
    return total


def build_results(ib_modules, pr_modules, process_label):
    metric_names = [metric_name for metric_name, _unit in METRIC_SPECS]
    results = {
        "resources": [{"name": metric_name, "unit": unit} for metric_name, unit in METRIC_SPECS],
        "total": {"type": "Process", "label": process_label},
        "modules": [],
    }

    diff_from(
        metric_names,
        compute_total(ib_modules, process_label),
        compute_total(pr_modules, process_label),
        results["total"],
    )

    keys = sorted(set(ib_modules.keys()) | set(pr_modules.keys()))
    for key in keys:
        ib_module = ib_modules.get(key, {})
        pr_module = pr_modules.get(key, {})
        result = {
            "label": pr_module.get("label", ib_module.get("label", "")),
            "type": pr_module.get("type", ib_module.get("type", "")),
        }
        diff_from(metric_names, ib_module, pr_module, result)
        results["modules"].append(result)

    return results


def output_paths(pr_file):
    pr_realpath = os.path.realpath(pr_file)
    output_prefix = os.path.join(
        os.path.dirname(pr_realpath), "diff-" + os.path.basename(pr_realpath)
    )
    return output_prefix, output_prefix + ".html"


def main(argv):
    if len(argv) != 3:
        print(
            """Usage: moduleEventAllocMonitor-circles-diff.py IB_FILE PR_FILE
Diff the memoryReports section of two moduleEventAllocMonitor JSON files and write JSON and HTML outputs next to PR_FILE."""
        )
        return 1

    ib_file = argv[1]
    pr_file = argv[2]

    try:
        ib_modules = load_reports(ib_file)
        pr_modules = load_reports(pr_file)
    except (OSError, ValueError, json.JSONDecodeError) as err:
        print("Error:", err)
        return 1

    process_label = os.path.basename(os.path.realpath(pr_file))
    results = build_results(ib_modules, pr_modules, process_label)

    dump_file, summary_file = output_paths(pr_file)
    with open(dump_file, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)

    template_file = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "module_event_alloc_monitor_viewer.html"
    )
    summary_html = build_viewer_html(
        template_path=template_file,
        embedded_data=results,
        source_label="embedded moduleEventAllocMonitor diff data",
    )
    with open(summary_file, "w", encoding="utf-8") as handle:
        handle.write(summary_html)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
