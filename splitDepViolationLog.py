#!/usr/bin/env python

from __future__ import print_function

import os
import re
import sys
import time


class DepViolSplitter(object):
    def __init__(self, outFileIn=None, verbIn=False):

        self.outFile = sys.stdout
        if outFileIn:
            print("Summary file:", outFileIn)
            self.outFile = open(outFileIn, "w")

        self.verbose = verbIn

        return

    def __del__(self):
        self.outFile.close()
        return

    def setVerbose(self, verbIn=False):
        self.verbose = verbIn
        return

    # --------------------------------------------------------------------------------

    def split(self, logFile):

        self.outFile.write("going to check " + logFile + "\n")

        pkgStartRe = re.compile(r"^>> Checking dependency for (.*)\s*$")
        pkgEndRe = re.compile(r"^>> Done Checking dependency for (.*)\s*$")

        depViolRe = re.compile(r"\s*\*+ERROR: Dependency violation")

        logDirs = os.path.join(os.path.split(logFile)[0], "depViolationLogs")
        print("logDirs ", logDirs)
        if not os.path.exists(logDirs):
            os.makedirs(logDirs)

        lf = open(logFile, "r")
        lines = lf

        startTime = time.time()
        nLines = 0
        pkgViol = {}

        actPkg = "None"
        actTstLines = 0
        actPkgLines = 0

        actLogLines = []
        startFound = False
        for line in lines:

            # write out log to individual log file ...
            if startFound and ">> Done Checking dependency " not in line:
                actLogLines.append(line)

            nLines += 1
            actTstLines += 1
            actPkgLines += 1

            pkgStartMatch = pkgStartRe.match(line)
            if pkgStartMatch:
                pkg = pkgStartMatch.group(1)
                actPkg = pkg
                actPkgLines = 0
                startFound = True

            pkgEndMatch = pkgEndRe.match(line)
            if pkgEndMatch:
                pkg = pkgEndMatch.group(1)
                if actPkg != pkg:
                    self.outFile.write(
                        "pkgEndMatch> package mismatch: pkg found "
                        + pkg
                        + " actPkg="
                        + actPkg
                        + "\n"
                    )

                if len(actLogLines) > 2:
                    pkgViol[pkg] = len(depViolRe.findall("".join(actLogLines)))
                    actLogDir = os.path.join(logDirs, pkg)
                    ################################################
                    if not os.path.exists(actLogDir):
                        os.makedirs(actLogDir)
                    # os.makedirs(actLogDir)
                    ###############################################
                    actLogFile = open(os.path.join(actLogDir, "depViolation.log"), "w")
                    actLogFile.write("".join(actLogLines))
                    actLogFile.close()
                    actLogLines = []
                startFound = False

        stopTime = time.time()
        lf.close()

        self.outFile.write("found a total of " + str(nLines) + " lines in logfile.\n")
        self.outFile.write("analysis took " + str(stopTime - startTime) + " sec.\n")

        self.outFile.write(
            "total number of packages with violations: " + str(len(list(pkgViol.keys()))) + "\n"
        )

        import pprint

        pprint.pprint(pkgViol)

        try:
            from pickle import Pickler

            resFile = open("depViolationSummary.pkl", "wb")
            pklr = Pickler(resFile, protocol=2)
            pklr.dump(pkgViol)
            resFile.close()
            print("Successfully pickled results for dependency violations ! ")
        except Exception as e:
            print("ERROR during pickling results for dependency violations:", str(e))

        return


# ================================================================================
def main():
    try:
        import argparse
    except ImportError:
        import archived_argparse as argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-l", "--logFile", default=None, required=True)
    parser.add_argument("-v", "--verbose", action="store_true", default=False)
    parser.add_argument("-s", "--outFile", default=None)
    args = parser.parse_args()

    logFile = args.logFile
    verb = args.verbose
    outFile = args.outFile

    tls = DepViolSplitter(outFileIn=outFile, verbIn=verb)
    tls.split(logFile)


if __name__ == "__main__":
    main()
