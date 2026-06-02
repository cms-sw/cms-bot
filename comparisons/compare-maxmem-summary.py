#!/usr/bin/env python3
"""
Script to summarise the outputs of compare-maxmem.py
"""

from __future__ import print_function
import argparse
import os
import json
import glob
import re
import sys

import maxmem_threshold

VIEWER_TEMPLATE = "maxmem_summary_viewer.html"


def KILL(message):
    raise RuntimeError(message)


def WARNING(message):
    print(">> Warning -- " + message)


def is_raw_maxmem_comparison(json_dict):
    required_keys = ["max memory pr", "max memory base", "max memory pdiffs", "workflow"]
    return all(key in json_dict for key in required_keys)


def workflow_sort_key(workflow):
    try:
        return float(re.sub("_.*", "", workflow))
    except ValueError:
        return sys.maxsize


def step_sort_key(step):
    try:
        return int(step.replace("step", ""))
    except ValueError:
        return sys.maxsize


def build_viewer_html(template_path, embedded_data, source_label):
    with open(template_path, encoding="utf-8") as template_file:
        content = template_file.read()

    embedded_json = json.dumps(embedded_data).replace("</", "<\\/")

    autoload_snippet = """
    <script id="embedded-maxmem-summary-data" type="application/json">%s</script>
    <script>
        (function () {
            var dataNode = document.getElementById("embedded-maxmem-summary-data");
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


def build_summary_payload(workflows, results_url):
    ordered_workflows = sorted(workflows.keys(), key=workflow_sort_key)
    ordered_steps = sorted(
        {step for workflow in workflows.values() for step in workflow.keys()}, key=step_sort_key
    )
    return {
        "workflows": workflows,
        "orderedWorkflows": ordered_workflows,
        "orderedSteps": ordered_steps,
        "resultsURL": results_url,
        "defaultWarnThreshold": float(maxmem_threshold.WARN_THRESHOLD),
        "defaultErrorThreshold": float(maxmem_threshold.ERROR_THRESHOLD),
    }


def compare_maxmem_summary(**kwargs):
    inputDir = kwargs.get("inputDir")
    filePattern = kwargs.get("filePattern")
    summaryFilePath = kwargs.get("outputFile")
    summaryFormat = kwargs.get("outputFormat")
    dryRun = kwargs.get("dryRun", False)
    verbosity = kwargs.get("verbosity", 0)
    resultsURL = kwargs.get("resultsURL")

    inputFiles = glob.glob(os.path.join(inputDir, filePattern))

    workflows = {}
    for inputFile in sorted(inputFiles):
        with open(inputFile, "r") as f:
            jsonDict = json.load(f)
        if not is_raw_maxmem_comparison(jsonDict):
            if verbosity > 0:
                WARNING(
                    "compare-maxmem-summary -- skipping non-comparison json file: " + inputFile
                )
            continue
        max_memory_pr_dict = jsonDict["max memory pr"]
        max_memory_base_dict = jsonDict["max memory base"]
        max_memory_pdiff_dict = jsonDict["max memory pdiffs"]
        workflow = jsonDict["workflow"]
        threshold = float(jsonDict["threshold"])
        error_threshold = float(jsonDict["error_threshold"])
        if workflow not in workflows:
            workflows[workflow] = {}
            for step in max_memory_pr_dict.keys():
                max_mem_pr = max_memory_pr_dict[step].get("max memory used")
                req_mem_pr = max_memory_pr_dict[step].get("total memory requested")
                leak_mem_pr = max_memory_pr_dict[step].get("presently used")
                nalloc_pr = max_memory_pr_dict[step].get("# allocations calls")
                ndalloc_pr = max_memory_pr_dict[step].get("# deallocations calls")
                nlalloc_pr = nalloc_pr - ndalloc_pr if (nalloc_pr and ndalloc_pr) else 0
                max_memory_pr = max_mem_pr / (1024 * 1024) if max_mem_pr else 0.0
                req_memory_pr = req_mem_pr / (1024 * 1024) if req_mem_pr else 0.0
                leak_memory_pr = leak_mem_pr / (1024 * 1024) if leak_mem_pr else 0.0
                nallocated_pr = nalloc_pr if nalloc_pr else 0

                max_mem_base = max_memory_base_dict[step].get("max memory used")
                req_mem_base = max_memory_base_dict[step].get("total memory requested")
                leak_mem_base = max_memory_base_dict[step].get("presently used")
                nalloc_base = max_memory_base_dict[step].get("# allocations calls")
                ndalloc_base = max_memory_base_dict[step].get("# deallocations calls")
                nlalloc_base = nalloc_base - ndalloc_base if (nalloc_base and ndalloc_base) else 0
                max_memory_base = max_mem_base / (1024 * 1024) if max_mem_base else 0.0
                req_memory_base = req_mem_base / (1024 * 1024) if req_mem_base else 0.0
                leak_memory_base = leak_mem_base / (1024 * 1024) if leak_mem_base else 0.0
                nallocated_base = nalloc_base if nalloc_base else 0

                max_mem_pdiff = max_memory_pdiff_dict[step].get("max memory used")
                req_mem_pdiff = max_memory_pdiff_dict[step].get("total memory requested")
                leak_mem_pdiff = max_memory_pdiff_dict[step].get("presently used")
                nalloc_pdiff = max_memory_pdiff_dict[step].get("# allocations calls")
                max_memory_adiff = (
                    max_memory_pr - max_memory_base if (max_mem_pr and max_mem_base) else 0.0
                )
                max_memory_pdiff = (
                    100 * (max_mem_pr - max_mem_base) / max_mem_base
                    if (max_mem_pr and max_mem_base)
                    else 0.0
                )
                req_memory_adiff = req_memory_pr - req_memory_base
                req_memory_pdiff = (
                    100 * (req_mem_pr - req_mem_base) / req_mem_base
                    if (req_mem_pr and req_mem_base)
                    else 0.0
                )
                leak_memory_adiff = leak_memory_pr - leak_memory_base
                leak_memory_pdiff = (
                    100 * (leak_mem_pr - leak_mem_base) / leak_mem_base
                    if (leak_mem_pr and leak_mem_base)
                    else 0.0
                )
                nallocated_adiff = nallocated_pr - nallocated_base
                nallocated_pdiff = (
                    100 * (nalloc_pr - nalloc_base) / nalloc_base
                    if (nalloc_pr and nalloc_base)
                    else 0.0
                )
                nlallocated_adiff = nlalloc_pr - nlalloc_base
                nlallocated_pdiff = (
                    100 * (nlalloc_pr - nlalloc_base) / nlalloc_base
                    if (nlalloc_pr and nlalloc_base)
                    else 0.0
                )
                workflows[workflow][step] = {
                    "max memory pr": max_memory_pr,
                    "max memory base": max_memory_base,
                    "max memory pdiff": max_memory_pdiff,
                    "max memory adiff": max_memory_adiff,
                    "req memory pr": req_memory_pr,
                    "req memory base": req_memory_base,
                    "req memory pdiff": req_memory_pdiff,
                    "req memory adiff": req_memory_adiff,
                    "leak memory pr": leak_memory_pr,
                    "leak memory base": leak_memory_base,
                    "leak memory pdiff": leak_memory_pdiff,
                    "leak memory adiff": leak_memory_adiff,
                    "nallocated pr": nallocated_pr,
                    "nallocated base": nallocated_base,
                    "nallocated pdiff": nallocated_pdiff,
                    "nallocated adiff": nallocated_adiff,
                    "leaked alloc pr": nlalloc_pr,
                    "leaked alloc base": nlalloc_base,
                    "leaked alloc adiff": nlallocated_adiff,
                    "leaked alloc pdiff": nlallocated_pdiff,
                    "threshold": threshold,
                    "error_threshold": error_threshold
                }
    dumpfile = "maxmem-summary.json"
    with open(dumpfile, "w") as f:
        json.dump(workflows, f, indent=2)

    summaryHtml = ""
    if summaryFormat == "html":
        payload = build_summary_payload(workflows, resultsURL)
        viewer_template = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), VIEWER_TEMPLATE
        )
        summaryHtml = build_viewer_html(viewer_template, payload, "embedded maxmem summary")

    if dryRun:
        return 0

    if summaryHtml:
        if os.path.exists(summaryFilePath):
            if verbosity > 0:
                WARNING(
                    "compare-maxmem-summary -- target output file already exists (summary will not be produced)"
                )
        else:
            with open(summaryFilePath, "w") as summaryFile:
                summaryFile.write(summaryHtml)

    return


#### main
if __name__ == "__main__":
    ### args
    parser = argparse.ArgumentParser(
        prog="./" + os.path.basename(__file__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "-i",
        "--input-dir",
        dest="input_dir",
        action="store",
        default=None,
        required=True,
        help="path to input directory",
    )

    parser.add_argument(
        "-f",
        "--file-pattern",
        dest="file_pattern",
        action="store",
        default="*.json",
        help='pattern to select files in the input directory (default: "*.json")',
    )

    parser.add_argument(
        "-o",
        "--output-file",
        dest="output_file",
        action="store",
        default=None,
        required=True,
        help="path to output file (summary of comparisons)",
    )

    parser.add_argument(
        "-F",
        "--output-format",
        dest="output_format",
        action="store",
        default="html",
        choices=["html"],
        help='format of output file (must be "html") (default: "html")',
    )

    parser.add_argument(
        "-d",
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="enable dry-run mode (default: False)",
    )

    parser.add_argument(
        "-u",
        "--results-url",
        dest="results_url",
        action="store",
        default=None,
        required=True,
        help="url for pull request integration results",
    )

    parser.add_argument(
        "-v",
        "--verbosity",
        dest="verbosity",
        type=int,
        default=0,
        help="level of verbosity (default: 0)",
    )

    opts, opts_unknown = parser.parse_known_args()
    ### -------------------------

    # check: unrecognized command-line arguments
    if len(opts_unknown) > 0:
        KILL("unrecognized command-line arguments: " + str(opts_unknown))

    # check: input directories
    if not os.path.isdir(opts.input_dir):
        KILL("invalid path to input directory [-i]: " + opts.input_dir)

    # check: output
    outFile = opts.output_file
    if not opts.dry_run and os.path.exists(outFile):
        KILL("target output file already exists [-o]: " + outFile)

    # analyse inputs and produce summary
    compare_maxmem_summary(
        **{
            "inputDir": opts.input_dir,
            "filePattern": opts.file_pattern,
            "outputFile": outFile,
            "outputFormat": opts.output_format,
            "dryRun": opts.dry_run,
            "verbosity": opts.verbosity,
            "resultsURL": opts.results_url,
        }
    )
