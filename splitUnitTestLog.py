#!/usr/bin/env python

from __future__ import print_function
import os, sys, re, time


class LogSplitter(object):
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

        subsysRe = re.compile('^>> Tests for package ([A-Z].*/[A-Z].*) ran.')

        pkgTestStartRe = re.compile('^===== Test \"(.*)\" ====')
        pkgTestEndRe = re.compile('^\^\^\^\^ End Test (.*) \^\^\^\^')
        pkgTestResultRe = re.compile('.*---> test ([^ ]+) (had ERRORS|succeeded)')

        pkgStartRe = re.compile("^>> Entering Package (.*)")
        # pkgEndRe   = re.compile("^>> Leaving Package (.*)")
        pkgEndRe = re.compile("^>> Tests for package (.*) ran.")

        infoPkg = {}
        pkgSubsysMap = {}
        subsysPkgMap = {}

        baseDir = os.path.split(logFile)[0]
        logDirs = os.path.join(baseDir, 'unitTestLogs')
        print("logDirs ", logDirs)
        if not os.path.exists(logDirs):
            os.makedirs(logDirs)

        lf = open(logFile,"rb")
        lines = lf

        startTime = time.time()
        nLines = 0
        testNames = {}
        testLines = {}
        pkgLines = {}
        results = {}
        pkgTests = {}

        actPkg = "None"
        actTest = "None"
        actTstLines = 0
        actPkgLines = 0

        actLogLines = []
        startFound = False
        for line in lines:
            line = line.decode("ascii", errors='ignore')
            # write out log to individual log file ...
            if startFound and ">> Leaving Package " not in line:
                actLogLines.append(line)

            nLines += 1
            actTstLines += 1
            actPkgLines += 1
            subsysMatch = subsysRe.match(line)
            if subsysMatch:
                subsys, pkg = subsysMatch.group(1).split('/')
                if pkg not in pkgSubsysMap:
                    pkgSubsysMap[pkg] = subsys
                if subsys in subsysPkgMap:
                    subsysPkgMap[subsys].append(pkg)
                else:
                    subsysPkgMap[subsys] = [pkg]

            pkgStartMatch = pkgStartRe.match(line)
            if pkgStartMatch:
                pkg = pkgStartMatch.group(1)
                actPkg = pkg
                pkgTests[pkg] = 0
                actPkgLines = 0
                startFound = True

            pkgEndMatch = pkgEndRe.match(line)
            if pkgEndMatch:
                pkg = pkgEndMatch.group(1)
                if actPkg != pkg:
                    self.outFile.write("pkgEndMatch> package mismatch: pkg found " + pkg + ' actPkg=' + actPkg + '\n')
                pkgLines[pkg] = actPkgLines

                if len(actLogLines) > 2:
                    actLogDir = os.path.join(logDirs, pkg)
                    os.makedirs(actLogDir)
                    actLogFile = open(os.path.join(actLogDir, 'unitTest.log'), 'w')
                    actLogFile.write("".join(actLogLines))
                    actLogFile.close()
                    actLogLines = []
                startFound = False

            pkgTestResultMatch = pkgTestResultRe.match(line)
            if pkgTestResultMatch:  # this seems to only appear if there is an ERROR
                tstName = pkgTestResultMatch.group(1)
                results[tstName] = pkgTestResultMatch.group(2)

            pkgTestStartMatch = pkgTestStartRe.match(line)
            if pkgTestStartMatch:
                tst = pkgTestStartMatch.group(1)
                actTest = tst
                actTstLines = 0
                pkgTests[actPkg] += 1
                if actPkg in testNames:
                    testNames[actPkg].append(actTest)
                else:
                    testNames[actPkg] = [actTest]
                if actTest not in results:
                    results[actTest] = "succeeded"  # set the default, no error seen yet

            pkgTestEndMatch = pkgTestEndRe.match(line)
            if pkgTestEndMatch:
                tst = pkgTestEndMatch.group(1)
                if actTest != tst:
                    self.outFile.write(
                        "pkgTestEndMatch> package mismatch: pkg found " + pkg + ' actPkg=' + actPkg + '\n')
                testLines[tst] = actTstLines

        stopTime = time.time()
        lf.close()

        self.outFile.write("found a total of " + str(nLines) + ' lines in logfile.\n')
        self.outFile.write("analysis took " + str(stopTime - startTime) + ' sec.\n')

        self.outFile.write("total number of tests: " + str(len(list(results.keys()))) + '\n')
        nMax = 1000
        self.outFile.write("tests with more than " + str(nMax) + " lines of logs:\n")
        for pkg, lines in list(testLines.items()):
            if lines > nMax: self.outFile.write("  " + pkg + ' : ' + str(lines) + '\n')

        self.outFile.write("Number of tests for packages: \n")
        noTests = 0
        nrTests = 0
        indent = '    '
        totalOK = 0
        totalFail = 0
        unitTestResults = {}
        for pkg, nTst in list(pkgTests.items()):
            if nTst == 0:
                noTests += 1
            else:
                nrTests += 1
                if self.verbose: self.outFile.write('-' * 80 + '\n')
                self.outFile.write(indent + pkg + ' : ')
                nOK = 0
                if self.verbose: self.outFile.write("\n")
                for tNam in testNames[pkg]:
                    if results[tNam] == 'succeeded':
                        nOK += 1
                        totalOK += 1
                    else:
                        totalFail += 1
                    if self.verbose:
                        self.outFile.write(indent * 2 + tNam + ' ' + results[tNam] + '\n')
                if self.verbose: self.outFile.write(indent + pkg + " : ")
                self.outFile.write(
                    indent + str(len(testNames[pkg])) + ' tests in total,  OK:' + str(nOK) + ' fail:' + str(
                        len(testNames[pkg]) - nOK) + '\n')
                unitTestResults[pkg] = [testNames[pkg], nOK, len(testNames[pkg]) - nOK]

        self.outFile.write(indent + str(nrTests) + " packages  with   tests (" + str(
            float(nrTests) / float(len(list(pkgTests.keys())))) + ")\n")
        self.outFile.write(indent + str(noTests) + " packages without tests (" + str(
            float(noTests) / float(len(list(pkgTests.keys())))) + ")\n")
        self.outFile.write(indent + "in total:  tests OK : " + str(totalOK) + ' tests FAIL : ' + str(totalFail) + '\n')

        try:
            from pickle import Pickler
            resFile = open(baseDir + '/unitTestResults.pkl', 'wb')
            pklr = Pickler(resFile, protocol=2)
            pklr.dump(unitTestResults)
            pklr.dump(results)
            resFile.close()
            print("Successfully pickled results for unit tests ! ")
        except Exception as e:
            print("ERROR during pickling results for unit tests:", str(e))

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

    tls = LogSplitter(outFileIn=outFile, verbIn=verb)
    tls.split(logFile)
