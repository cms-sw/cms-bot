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

MAXMEM_WARN_THRESHOLD = 1.0
MAXMEM_ERROR_THRESHOLD = 10.0


def KILL(message):
    raise RuntimeError(message)


def WARNING(message):
    print(">> Warning -- " + message)


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
        max_memory_pr_dict = jsonDict["max memory pr"]
        max_memory_base_dict = jsonDict["max memory base"]
        max_memory_pdiff_dict = jsonDict["max memory pdiffs"]
        workflow = jsonDict["workflow"]
        threshold = float(jsonDict["threshold"])
        if workflow not in workflows:
            workflows[workflow] = {}
            for step in max_memory_pr_dict.keys():
                max_mem_pr = max_memory_pr_dict[step].get("max memory used")
                req_mem_pr = max_memory_pr_dict[step].get("total memory requested")
                leak_mem_pr = max_memory_pr_dict[step].get("presently used")
                nalloc_pr = max_memory_pr_dict[step].get("# allocations calls")
                ndalloc_pr = max_memory_pr_dict[step].get("# deallocations calls")
                nlalloc_pr = nalloc_pr - ndalloc_pr if (nalloc_pr and ndalloc_pr) else 0
                max_memory_pr = max_mem_pr / 1000000 if max_mem_pr else 0.0
                req_memory_pr = req_mem_pr / 1000000 if req_mem_pr else 0.0
                leak_memory_pr = leak_mem_pr / 1000000 if leak_mem_pr else 0.0
                nallocated_pr = nalloc_pr if nalloc_pr else 0

                max_mem_base = max_memory_base_dict[step].get("max memory used")
                req_mem_base = max_memory_base_dict[step].get("total memory requested")
                leak_mem_base = max_memory_base_dict[step].get("presently used")
                nalloc_base = max_memory_base_dict[step].get("# allocations calls")
                ndalloc_base = max_memory_base_dict[step].get("# deallocations calls")
                nlalloc_base = nalloc_base - ndalloc_base if (nalloc_base and ndalloc_base) else 0
                max_memory_base = max_mem_base / 1000000 if max_mem_base else 0.0
                req_memory_base = req_mem_base / 1000000 if req_mem_base else 0.0
                leak_memory_base = leak_mem_base / 1000000 if leak_mem_base else 0.0
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
                }

    def wffn(w):
        return float(re.sub("_.*", "", w))

    sortedworkflows = sorted(workflows.keys(), key=wffn)
    print(sortedworkflows)
    summaryLines = []
    if summaryFormat == "html":
        summaryLines += [
            "<html>",
            "<head><style>"
            + "table, th, td {border: 1px solid black;}</style>"
            + "<style> th, td {padding: 15px;}</style>"
            + "<style> tr:hover {background-color: yellow}</style>"
            + "<style> .noborder {}</style>"
            +"</head>",
            "<body><h3>Summary of Maxmem Profiler Comparisons</h3><table>",
            '<tr><th align="center">Workflow</th>'
            + '<th align="center">Quantity</th>'
            + '<th align="center">Legend</th>'
            + '<th align="center">Step1</th>'
            + '<th align="center">Step2</th>'
            + '<th align="center">Step3</th>'
            + '<th align="center">Step4</th>'
            + '<th align="center">Step5</th>'
            + '<th align="center">Step6</th>'
            + '<th align="center">Step7</th>'
            + '<th align="center">Step8</th>'
            + '<th align="center">Step9</th>'
            + '<th align="center">Step10</th>'
            + '<th align="center">Step11</th>'
            + "</tr>",
        ]

    def stepfn(step):
        return int(step.replace("step", ""))

    for workflow in sortedworkflows:
        summaryLine = []
        if summaryFormat == "html":
            summaryLine += [
                "<tr>",
                '  <td rowspan="26"><a href="'
                + resultsURL
                + '/%s/">' % workflow
                + "%s</a></td>" % workflow,
            ]

        summaryLine += ['<tr><th rowspan="5" style="white-space:nowrap"> max memory used:</th>']
        summaryLine += ['<tr><td style="border-bottom-style: hidden;">&lt;pull request (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["max memory pr"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["max memory base"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;PR - baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["max memory adiff"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-top-style:hidden">&lt;100 * (PR - baseline)/baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            threshold = workflows[workflow][step]["threshold"]
            if not threshold:
                threshold = 1.0
            error_threshold = workflows[workflow][step].get("error_threshold")
            if not error_threshold:
                error_threshold = 10.0
            cellString = "<td "
            color = ""
            if abs(workflows[workflow][step]["max memory pdiff"]) > MAXMEM_WARN_THRESHOLD:
                color = 'bgcolor="orange"'
            if abs(workflows[workflow][step]["max memory pdiff"]) > MAXMEM_ERROR_THRESHOLD:
                color = 'bgcolor="red"'
            cellString += color
            cellString += ">"
            summaryLine += [
                cellString,
                "{:,.3f}".format(workflows[workflow][step]["max memory pdiff"]),
                "%</td>",
            ]
        summaryLine += [
            "</tr>",
        ]

        summaryLine += [
            '<tr><th rowspan="5" style="white-space:nowrap"> total memory request:</th>'
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;"> &lt;pull request (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["req memory pr"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["req memory base"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;PR - baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["req memory adiff"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-top-style:hidden;">&lt;100 * (PR - baseline)/baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.3f}".format(workflows[workflow][step]["req memory pdiff"]),
                "%</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><th rowspan="5" style="white-space:nowrap"> # allocation calls:</th>']
        summaryLine += ['<tr><td style="border-bottom-style:hidden;">&lt;pull request &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated pr"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated base"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;PR - baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated adiff"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-top-style:hidden;">&lt;100 * (PR - baseline)/baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.3f}".format(workflows[workflow][step]["nallocated pdiff"]),
                "%</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><th rowspan="5" style="white-space:nowrap"> memory leaked:</th>']
        summaryLine += ['<tr><td style="border-bottom-style:hidden;">&lt;pull request (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["leak memory pr"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["leak memory base"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;PR - baseline (MB)&gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.2f}".format(workflows[workflow][step]["leak memory adiff"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-top-style:hidden;">&lt;100 * (PR - baseline)/baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.3f}".format(workflows[workflow][step]["leak memory pdiff"]),
                "%</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += [
            '<tr><th rowspan="5" style="white-space:nowrap"> # allocation calls leaked:</th>'
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;">&lt;pull request &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated pr"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated base"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-bottom-style:hidden;border-top-style:hidden;">&lt;PR - baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,}".format(workflows[workflow][step]["nallocated adiff"]),
                "</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLine += ['<tr><td style="border-top-style:hidden;">&lt;100 * (PR - baseline)/baseline &gt;</td>']
        for step in sorted(workflows[workflow].keys(), key=stepfn):
            summaryLine += [
                "<td>",
                "{:,.3f}".format(workflows[workflow][step]["nallocated pdiff"]),
                "%</td>",
            ]
        summaryLine += [
            "</tr>",
        ]
        summaryLines += summaryLine

    if summaryFormat == "html":
        summaryLines += [
            '</table><table><tr><td bgcolor="orange">'
            + "maximum memory used warn threshold %0.3f" % MAXMEM_WARN_THRESHOLD
            + '%</td></tr><tr><td bgcolor="red">'
            + "maximum memory used error threshold %0.3f" % MAXMEM_ERROR_THRESHOLD
            + "%</td></tr>",
        ]
        summaryLines += ["</table></body></html>"]

    if dryRun:
        return 0

    if summaryLines:
        if os.path.exists(summaryFilePath):
            if verbosity > 0:
                WARNING(
                    "compare-maxmem-summary -- target output file already exists (summary will not be produced)"
                )
        else:
            with open(summaryFilePath, "w") as summaryFile:
                for _tmp in summaryLines:
                    summaryFile.write(_tmp + "\n")

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
