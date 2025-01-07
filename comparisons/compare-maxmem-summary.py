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
                max_memory_pr = max_mem_pr / 1000000 if max_mem_pr else 0.0
                req_memory_pr = req_mem_pr / 1000000 if req_mem_pr else 0.0
                leak_memory_pr = leak_mem_pr / 1000000 if leak_mem_pr else 0.0
                nallocated_pr = nalloc_pr if nalloc_pr else 0

                max_mem_base = max_memory_base_dict[step].get("max memory used")
                req_mem_base = max_memory_base_dict[step].get("total memory requested")
                leak_mem_base = max_memory_base_dict[step].get("presently used")
                nalloc_base = max_memory_base_dict[step].get("# allocations calls")
                max_memory_base = max_mem_base / 1000000 if max_mem_base else 0.0
                req_memory_base = req_mem_base / 1000000 if req_mem_base else 0.0
                leak_memory_base = leak_mem_base / 1000000 if leak_mem_base else 0.0
                nallocated_base = nalloc_base if nalloc_pr else 0

                max_mem_pdiff = max_memory_pdiff_dict[step].get("max memory used")
                req_mem_pdiff = max_memory_pdiff_dict[step].get("total memory requested")
                leak_mem_pdiff = max_memory_pdiff_dict[step].get("presently used")
                nalloc_pdiff = max_memory_pdiff_dict[step].get("# allocations calls")
                max_memory_adiff = max_memory_pr - max_memory_base
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
                    "threshold": threshold,
                }

    def wffn(w):
        return float(re.sub("_.*", "", w))

    sortedworkflows = sorted(workflows.keys(), key=wffn)

    summaryLines = []
    if summaryFormat == "html":
        summaryLines += [
            "<html>",
            "<head><style>"
            + "table, th, td {border: 1px solid black;}</style>"
            + "<style> th, td {padding: 15px;}</style></head>",
            "<body><h3>Summary of Maxmem Profiler Comparisons</h3><table>",
            '<tr><th align="center">Workflow</th>'
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
    elif summaryFormat == "txt":
        summaryLines += [
            "| {:25} | {:25} | {:15} | {:10} | {:10}".format(
                "Pull request max mem used",
                "Base release max mem used",
                "Percentage diff",
                "Step",
                "Workflow",
            )
        ]
        summaryLines += ["-" * 100]

    def stepfn(step):
        return int(step.replace("step", ""))

    max_mem_pr, max_mem_base, max_mem_pdiff = 0, 0, 0
    for workflow in sortedworkflows:
        summaryLine = []
        if summaryFormat == "html":
            summaryLine += [
                "<tr>",
                '  <td align="left"><a href="'
                + resultsURL
                + '/%s/">' % workflow
                + "%s</a></td>" % workflow,
                '<td style="white-space:nowrap"><b>max memory used:</b><BR>&lt;baseline (MB)&gt;<BR>&lt;pull request (MB)&gt;<BR>&lt PR - baseline&gt<BR>&lt;100* (PR - baseline)/baseline&gt;<BR>',
                 "<b>total memory requested:</b><BR>&lt;baseline (MB)&gt;<BR>&lt;pull request (MB)&gt;<BR>&lt PR - baseline&gt<BR>&lt;100* (PR - baseline)/baseline&gt;<BR>",
                 "<b>memory leaked:</b><BR>&lt;baseline (MB)&gt;<BR>&lt;pull request (MB)&gt;<BR>&lt PR - baseline&gt<BR>&lt;100* (PR - baseline)/baseline&gt;<BR>",
                 "<b>#allocation calls:</b><BR>&lt;baseline (MB)&gt;<BR>&lt;pull request (MB)&gt;<BR>&lt PR - baseline&gt<BR>&lt;100* (PR - baseline)/baseline&gt;<BR>",
            ]

        for step in sorted(workflows[workflow].keys(), key=stepfn):
            max_mem_pr = workflows[workflow][step]["max memory pr"]
            max_mem_base = workflows[workflow][step]["max memory base"]
            max_mem_pdiff = workflows[workflow][step]["max memory pdiff"]
            max_mem_adiff = workflows[workflow][step]["max memory adiff"]
            req_mem_pr = workflows[workflow][step]["req memory pr"]
            req_mem_base = workflows[workflow][step]["req memory base"]
            req_mem_pdiff = workflows[workflow][step]["req memory pdiff"]
            req_mem_adiff = workflows[workflow][step]["req memory adiff"]
            leak_mem_pr = workflows[workflow][step]["leak memory pr"]
            leak_mem_base = workflows[workflow][step]["leak memory base"]
            leak_mem_pdiff = workflows[workflow][step]["leak memory pdiff"]
            leak_mem_adiff = workflows[workflow][step]["leak memory adiff"]
            nalloc_pr = workflows[workflow][step]["nallocated pr"]
            nalloc_base = workflows[workflow][step]["nallocated base"]
            nalloc_pdiff = workflows[workflow][step]["nallocated pdiff"]
            nalloc_adiff = workflows[workflow][step]["nallocated adiff"]
            threshold = workflows[workflow][step]["threshold"]
            if not threshold:
                threshold = 1.0
            error_threshold = workflows[workflow][step].get("error_threshold")
            if not error_threshold:
                error_threshold = 10.0
            cellString = '<td align="right" '
            color = ""
            if abs(max_mem_pdiff) > threshold:
                color = 'bgcolor="orange"'
            if abs(max_mem_pdiff) > error_threshold:
                color = 'bgcolor="red"'
            cellString += color
            cellString += ">"
            if summaryFormat == "html":
                summaryLine += [
                    cellString
                    + "<br/>"
                    + "%0.2f<br/>" % max_mem_base
                    + "%0.2f<br/>" % max_mem_pr
                    + "%0.2f<br/>" % max_mem_adiff
                    + "%0.3f" % max_mem_pdiff
                    + "%<br/><br/>"
                    + "%0.2f<br/>" % req_mem_base
                    + "%0.2f<br/>" % req_mem_pr
                    + "%0.2f<br/>" % req_mem_adiff
                    + "%0.3f" % req_mem_pdiff
                    + "%<br/><br/>"
                    + "%0.2f<br/>" % leak_mem_base
                    + "%0.2f<br/>" % leak_mem_pr
                    + "%0.2f<br/>" % leak_mem_adiff
                    + "%0.3f" % leak_mem_pdiff
                    + "%<br/><br/>"
                    + "%i<br/>" % nalloc_base
                    + "%i<br/>" % nalloc_pr
                    + "%i<br/>" % nalloc_adiff
                    + "%0.3f" % nalloc_pdiff
                    + "%</td>"
                ]
            elif summaryFormat == "txt":
                summaryLines += [
                    "| {:25f} | {:25f} | {:15f} | {:10} | {:10}".format(
                        max_mem_base, max_mem_pr, max_mem_pdiff, step, workflow
                    )
                ]
        if summaryFormat == "html":
            summaryLine += ["</tr>"]
            summaryLines += summaryLine

        if summaryFormat == "txt":
            summaryLines += ["-" * 100]

    if summaryFormat == "html":
        summaryLines += [
            '</table><table><tr><td bgcolor="orange">'
            + "warn threshold %0.2f" % threshold
            + '%</td></tr><tr><td bgcolor="red">'
            + "error threshold %0.2f" % error_threshold
            + "%</td></tr>",
        ]
        summaryLines += ["</table></body></html>"]
    if summaryFormat == "txt":
        summaryLines += [
            "warn threshold %0.2f" % threshold,
            "error threshold %0.2f" % error_threshold,
            "max memory used:",
            "<pull request (MB)>",
            "<baseline (MB)>",
            "<100* (PR - baseline)/baseline>",
        ]

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
        default="txt",
        choices=["html", "txt"],
        help='format of output file (must be "txt" or "html") (default: "txt")',
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
