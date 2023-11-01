#!/usr/bin/env python
"""
Script to compare the content of edm::TriggerResults collections in EDM files across multiple workflows
 - CMSSW dependencies: edmDumpEventContent, hltDiff
"""
from __future__ import print_function
import argparse
import os
import fnmatch
import subprocess


def KILL(message):
    raise RuntimeError(message)


def WARNING(message):
    print(">> Warning -- " + message)


def get_output(cmds, permissive=False):
    prc = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = prc.communicate()
    if (not permissive) and prc.returncode:
        KILL(
            "get_output -- shell command failed (execute command to reproduce the error):\n"
            + " " * 14
            + "> "
            + cmd
        )
    return (out, err)


def command_output_lines(cmds, stdout=True, stderr=False, permissive=False):
    _tmp_out_ls = []
    if not (stdout or stderr):
        WARNING(
            'command_output_lines -- options "stdout" and "stderr" both set to FALSE, returning empty list'
        )
        return _tmp_out_ls

    _tmp_out = get_output(cmds, permissive=permissive)
    if stdout:
        _tmp_out_ls += _tmp_out[0].split("\n")
    if stderr:
        _tmp_out_ls += _tmp_out[1].split("\n")

    return _tmp_out_ls


def which(program, permissive=False, verbose=False):
    _exe_ls = []
    fpath, fname = os.path.split(program)
    if fpath:
        if os.path.isfile(program) and os.access(program, os.X_OK):
            _exe_ls += [program]
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
                _exe_ls += [exe_file]
    _exe_ls = list(set(_exe_ls))

    if len(_exe_ls) == 0:
        log_msg = "which -- executable not found: " + program
        if permissive:
            if verbose:
                WARNING(log_msg)
            return None
        else:
            KILL(log_msg)

    if verbose and len(_exe_ls) > 1:
        WARNING('which -- executable "' + program + '" has multiple matches: \n' + str(_exe_ls))

    return _exe_ls[0]


def getListOfTriggerResultsProcessNames(inputEDMFile, verbosity=0):
    ret = []
    try:
        for outl in command_output_lines(["edmDumpEventContent", inputEDMFile]):
            outl_split = [_tmp.replace('"', "") for _tmp in outl.split()]
            if len(outl_split) != 4:
                continue
            if (
                outl_split[0] == "edm::TriggerResults"
                and outl_split[1] == "TriggerResults"
                and outl_split[2] == ""
            ):
                ret.append(outl_split[3])
        ret = list(set(ret))
    except:
        if verbosity > 10:
            WARNING(
                'getListOfTriggerResultsProcessNames -- failed to execute "edmDumpEventContent '
                + inputEDMFile
                + '" (will return empty list)'
            )
    return ret


def compareTriggerResults(**kwargs):
    inputDir1 = kwargs.get("inputDir1")
    inputDir2 = kwargs.get("inputDir2")
    filePattern = kwargs.get("filePattern")
    outputDir = kwargs.get("outputDir")
    maxEvents = kwargs.get("maxEvents")
    summaryFormat = kwargs.get("summaryFormat", None)
    dryRun = kwargs.get("dryRun", False)
    verbosity = kwargs.get("verbosity", 0)

    files1 = [os.path.join(dp, f) for dp, dn, filenames in os.walk(inputDir1) for f in filenames]
    files1 = [f for f in files1 if fnmatch.fnmatch(f, filePattern)]

    files2 = [os.path.join(dp, f) for dp, dn, filenames in os.walk(inputDir2) for f in filenames]
    files2 = [f for f in files2 if fnmatch.fnmatch(f, filePattern)]

    wfDict = {}
    for f1 in sorted(files1):
        fBasename, wfName = os.path.basename(f1), os.path.dirname(os.path.relpath(f1, inputDir1))
        f2 = os.path.join(inputDir2, wfName, fBasename)
        if f2 not in files2:
            continue

        # get list of processNames of edm::TriggerResults collections
        trProcessNames = getListOfTriggerResultsProcessNames(f1, verbosity)
        if not trProcessNames:
            continue

        # remove duplicates across different EDM files of the same workflow
        # (would become unnecessary calls to hltDiff)
        trProcessNames2 = trProcessNames[:]
        for _tmp1 in trProcessNames:
            if wfName in wfDict:
                if _tmp1 in wfDict[wfName]:
                    trProcessNames2.remove(_tmp1)

        # skip if empty list
        if not trProcessNames2:
            continue

        # fill dictionary
        if wfName not in wfDict:
            wfDict[wfName] = {}
        for _tmp1 in trProcessNames2:
            wfDict[wfName][_tmp1] = [f1, f2]

    if not wfDict:
        if verbosity >= 0:
            WARNING(
                "compareTriggerResults -- found zero inputs to be compared (no outputs produced)"
            )
        return -1

    # hltDiff calls
    numWorkflowsChecked, numWorkflowsWithDiffs = 0, 0
    summaryLines = []

    if summaryFormat == "html":
        summaryLines += [
            "<html>",
            "<head><style> table { border-spacing: 18px; }</style></head>",
            "<body><h3>Summary of edm::TriggerResults Comparisons</h3><table>",
            "<tr><td>Workflow</td><td>Process Name</td><td>Events with Diffs</td><td>Events Processed</td></tr>",
        ]
    elif summaryFormat == "txt":
        summaryLines += [
            "| {:25} | {:18} | {:12} | {:}".format(
                "Events with Diffs", "Events Processed", "Process Name", "Workflow"
            )
        ]
        summaryLines += ["-" * 100]

    try:
        sortedWfNames = sorted(wfDict, key=lambda k: float(k.split("_")[0]))
    except:
        sortedWfNames = sorted(wfDict.keys())

    for wfName in sortedWfNames:
        wfNameShort = wfName.split("_")[0]
        wfOutputDir = os.path.join(outputDir, wfName)
        if not dryRun:
            try:
                os.makedirs(wfOutputDir)
            except:
                warn_msg = (
                    "target output directory already exists"
                    if os.path.isdir(wfOutputDir)
                    else "failed to create output directory"
                )
                WARNING(warn_msg + " (will skip comparisons for this workflow): " + wfOutputDir)
                continue

        wfHasDiff = False
        for procName in wfDict[wfName]:
            hltDiff_cmds = ["hltDiff"]
            hltDiff_cmds += ["-m", str(maxEvents)] * (maxEvents >= 0)
            hltDiff_cmds += ["-o", wfDict[wfName][procName][0], "-O", procName]
            hltDiff_cmds += ["-n", wfDict[wfName][procName][1], "-N", procName]
            hltDiff_cmds += ["-j", "-F", os.path.join(wfOutputDir, procName)]

            if dryRun:
                if verbosity > 0:
                    print("> " + " ".join(hltDiff_cmds))
                continue

            hltDiff_outputs = command_output_lines(hltDiff_cmds)

            diffStats = []
            with open(os.path.join(wfOutputDir, procName + ".log"), "w") as outputLogFile:
                for _tmp in hltDiff_outputs:
                    outputLogFile.write(_tmp + "\n")
                    # CAVEAT: relies on format of hltDiff outputs to stdout
                    #  - see https://github.com/cms-sw/cmssw/blob/master/HLTrigger/Tools/bin/hltDiff.cc
                    if _tmp.startswith("Found "):
                        diffStatsTmp = [int(s) for s in _tmp.split() if s.isdigit()]
                        if len(diffStatsTmp) == 2:
                            if diffStats:
                                WARNING(
                                    "logic error -- hltDiff statistics already known (check output of hltDiff)"
                                )
                            else:
                                diffStats = diffStatsTmp[:]
                        else:
                            WARNING(
                                "format error -- extracted N!=2 integers from output of hltDiff: "
                                + str(diffStatsTmp)
                            )

            if not diffStats:
                diffStats = [0, 0]
            wfHasDiff |= diffStats[1] > 0

            if summaryFormat == "html":
                summaryLines += [
                    "<tr>",
                    '  <td align="left"><a href="' + wfName + '">' + wfNameShort + "</a></td>",
                    '  <td align="center"><a href="'
                    + os.path.join(wfName, procName + ".log")
                    + '">'
                    + procName
                    + "</a></td>",
                    '  <td align="right">' + str(diffStats[1]) + "</td>",
                    '  <td align="right">' + str(diffStats[0]) + "</td>",
                    "</tr>",
                ]
            elif summaryFormat == "txt":
                summaryLines += [
                    "| {:25d} | {:18d} | {:12} | {:}".format(
                        diffStats[1], diffStats[0], procName, wfName
                    )
                ]

        numWorkflowsChecked += 1
        if wfHasDiff:
            numWorkflowsWithDiffs += 1

        if summaryFormat == "txt":
            summaryLines += ["-" * 100]

    if summaryFormat == "html":
        summaryLines += ["</table></body></html>"]

    if dryRun:
        return 0

    if summaryLines:
        outputSummaryFilePath = os.path.join(
            outputDir, "index.html" if summaryFormat == "html" else "summary.log"
        )
        with open(outputSummaryFilePath, "w") as outputSummaryFile:
            for _tmp in summaryLines:
                outputSummaryFile.write(_tmp + "\n")

    if verbosity >= 0:
        if numWorkflowsChecked == 0:
            print("SUMMARY TriggerResults: no workflows checked")
        elif numWorkflowsWithDiffs == 0:
            print("SUMMARY TriggerResults: no differences found")
        else:
            print(
                "SUMMARY TriggerResults: found differences in {:d} / {:d} workflows".format(
                    numWorkflowsWithDiffs, len(wfDict.keys())
                )
            )

    return numWorkflowsWithDiffs


#### main
if __name__ == "__main__":
    ### args
    parser = argparse.ArgumentParser(
        prog="./" + os.path.basename(__file__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )

    parser.add_argument(
        "-r",
        "--reference-dir",
        dest="inputDir_refe",
        action="store",
        default=None,
        required=True,
        help='path to directory with baseline (or, "reference") workflow outputs',
    )

    parser.add_argument(
        "-t",
        "--target-dir",
        dest="inputDir_targ",
        action="store",
        default=None,
        required=True,
        help='path to directory with new (or, "target") workflow outputs',
    )

    parser.add_argument(
        "-f",
        "--file-pattern",
        dest="file_pattern",
        action="store",
        default="*.root",
        help='pattern of input EDM files to be compared (default: "*.root")',
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        dest="outputDir",
        action="store",
        default=None,
        required=True,
        help="path to output directory",
    )

    parser.add_argument(
        "-m",
        "--max-events",
        dest="max_events",
        action="store",
        type=int,
        default=-1,
        help="maximum number of events considered per comparison (default: -1, i.e. all)",
    )

    parser.add_argument(
        "-s",
        "--summary",
        dest="summary",
        action="store",
        default=None,
        choices=["html", "txt"],
        help='produce summary file in the specified format (must be "txt" or "html") (default: None, i.e. no summary)',
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
    if not os.path.isdir(opts.inputDir_refe):
        KILL(
            'invalid path to directory with baseline (or, "reference") workflow outputs [-r]: '
            + opts.inputDir_refe
        )

    if not os.path.isdir(opts.inputDir_targ):
        KILL(
            'invalid path to directory with new (or, "target") workflow outputs [-t]: '
            + opts.inputDir_targ
        )

    # check: output
    outDir = opts.outputDir
    if not opts.dry_run and opts.summary is not None and os.path.exists(outDir):
        KILL("target output directory already exists [-o]: " + outDir)

    # check: external dependencies
    if which("edmDumpEventContent", permissive=True) is None:
        KILL(
            'executable "edmDumpEventContent" is not available (set up an appropriate CMSSW area)'
        )

    if which("hltDiff", permissive=True) is None:
        KILL('executable "hltDiff" is not available (set up an appropriate CMSSW area)')

    # run TriggerResults comparisons
    compareTriggerResults(
        **{
            "inputDir1": opts.inputDir_refe,
            "inputDir2": opts.inputDir_targ,
            "filePattern": opts.file_pattern,
            "outputDir": outDir,
            "maxEvents": opts.max_events,
            "summaryFormat": opts.summary,
            "dryRun": opts.dry_run,
            "verbosity": opts.verbosity,
        }
    )
