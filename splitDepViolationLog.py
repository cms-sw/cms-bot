#!/usr/bin/env python

from __future__ import print_function
import os, sys, re, time


class DepViolSplitter(object):
    def __init__(self, outFileIn=None, verbIn=False):

        self.outFile = sys.stdout
        if outFileIn:
            print("Summary file:", outFileIn)
            self.outFile = open(outFileIn, 'w')

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

        self.outFile.write("going to check " + logFile + '\n')

        pkgStartRe = re.compile('^>> Checking dependency for (.*)\s*$')
        pkgEndRe = re.compile('^>> Done Checking dependency for (.*)\s*$')

        depViolRe = re.compile('\s*\*+ERROR: Dependency violation')

        infoPkg = {}
        pkgSubsysMap = {}
        subsysPkgMap = {}

        logDirs = os.path.join(os.path.split(logFile)[0], 'depViolationLogs')
        print("logDirs ", logDirs)
        if not os.path.exists(logDirs):
            os.makedirs(logDirs)

        lf = open(logFile, 'r')
        lines = lf

        startTime = time.time()
        nLines = 0
        pkgViol = {}

        actPkg = "None"
        actTest = "None"
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
                    self.outFile.write("pkgEndMatch> package mismatch: pkg found " + pkg + ' actPkg=' + actPkg + '\n')

                if len(actLogLines) > 2:
                    pkgViol[pkg] = len(depViolRe.findall("".join(actLogLines)))
                    actLogDir = os.path.join(logDirs, pkg)
                    ################################################
                    if not os.path.exists(actLogDir):
                        os.makedirs(actLogDir)
                    # os.makedirs(actLogDir)
                    ###############################################
                    actLogFile = open(os.path.join(actLogDir, 'depViolation.log'), 'w')
                    actLogFile.write("".join(actLogLines))
                    actLogFile.close()
                    actLogLines = []
                startFound = False

        stopTime = time.time()
        lf.close()

        self.outFile.write("found a total of " + str(nLines) + ' lines in logfile.\n')
        self.outFile.write("analysis took " + str(stopTime - startTime) + ' sec.\n')

        self.outFile.write("total number of packages with violations: " + str(len(list(pkgViol.keys()))) + '\n')

        import pprint
        pprint.pprint(pkgViol)

        try:
            from pickle import Pickler
            resFile = open('depViolationSummary.pkl', 'wb')
            pklr = Pickler(resFile, protocol=2)
            pklr.dump(pkgViol)
            resFile.close()
            print("Successfully pickled results for dependency violations ! ")
        except Exception as e:
            print("ERROR during pickling results for dependency violations:", str(e))

        return


# ================================================================================

def usage():
    print("usage: " + os.path.basename(sys.argv[0]) + " --logFile <logFileName> [--verbose]\n")
    return


if __name__ == "__main__":
    import getopt

    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'hl:sv',
                                   ['help', 'logFile=', 'verbose', 'outFile='])
    except getopt.GetoptError:
        usage()
        sys.exit(-2)

    logFile = None
    verb = False
    outFile = None

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

        if o in ('-l', '--logFile',):
            logFile = a

        if o in ('-v', '--verbose',):
            verb = True

        if o in ('-l', '--outFile',):
            outFile = a

    if not logFile:
        usage()
        sys.exit(-1)

    tls = DepViolSplitter(outFileIn=outFile, verbIn=verb)
    tls.split(logFile)
