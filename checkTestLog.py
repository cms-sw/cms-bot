#!/usr/bin/env python

from __future__ import print_function
import os, sys, re, time

# TODO is this file used?

class TestLogChecker(object):
    def __init__(self, outFileIn=None, verbIn=False):

        self.outFile=sys.stdout
        if outFileIn:
            print("Summary file:", outFileIn)
            self.outFile=open(outFileIn, 'w')

        self.verbose = verbIn

        return

    def __del__(self):
        self.outFile.close()
        return

    def setVerbose(self, verbIn=False):
        self.verbose = verbIn
        return
    
    def checkScramWarnings(self, logFile, verbose=False):

        self.outFile.write("going to check "+ logFile+ ' for scram warnings\n')

        #"""
        #WARNING: Unable to find package/tool called Geometry/CommonDetAlgo
        #         in current project area (declared at src/RecoPixelVZero/PixelVZeroFinding/data)
        #
        #""""

        exprNoPkg  = '^WARNING: Unable to find package/tool called ([A-Za-z].*/[A-Za-z].*)'
        exprNoPkg += '\s*in current project area \(declared at src/([A-Za-z].*)\)'
        noPkgRe = re.compile(exprNoPkg)

        #WARNING: PhysicsTools/RecoAlgos/BuildFile does not export anything:
        noExportRe = re.compile('^WARNING: ([A-Za-a].*)/BuildFile does not export anything:')

        lf = open(logFile,'r')

        startTime = time.time()
        nLines = 0
        nNoPkg  = 0
        noToolPkgs  = []
        noExport = []
        testLines = {}
        pkgLines = {}
        prevLine = ""
        for line in lf:
            nLines += 1
            # merge with the previous line (w/o the <endline> to get the two-line warnings from scram
            both = prevLine[:-1] + line
            prevLine = line
            if both.find("WARNING:") == -1: continue

            # analyze what we got
            noPkgMatch = noPkgRe.match(both)
            if noPkgMatch:
                nNoPkg += 1
                pkg  = noPkgMatch.group(2).strip()
                tool = noPkgMatch.group(1).strip()
                tp = pkg+'--'+tool
                if tp not in noToolPkgs: noToolPkgs.append(tp)
                
            noExportMatch = noExportRe.match(both)
            if noExportMatch:
                buildFile = noExportMatch.group(1).strip()
                if buildFile not in noExport:
                    noExport.append(buildFile)


        lf.close()

        self.outFile.write( 'found '+ str(nNoPkg)+ ' scram-warnings in ' +str( nLines)+ ' lines of log file.\n')
        self.outFile.write( 'found ' + str(len(noToolPkgs))+ ' BuildFiles with tool problems\n')
        if verbose:
            for p in noToolPkgs: self.outFile.write( "    "+p+'\n')
            self.outFile.write('\n')
            
        self.outFile.write( 'found ' +str(len(noExport))+ ' BuildFiles without exporting anything:\n')
        if verbose:
            for p in noExport: self.outFile.write( "    "+ p+'\n')
            self.outFile.write('\n')

        self.outFile.write('\n')

        return

    # --------------------------------------------------------------------------------

    def check(self, logFile):

        self.outFile.write( "going to check "+ logFile+'\n')

        subsysRe = re.compile('^>> Tests for package ([A-Za-z].*/[A-Za-z].*) ran.')

        pkgTestStartRe  = re.compile('^===== Test \"(.*)\" ====')
        pkgTestEndRe    = re.compile('^\^\^\^\^ End Test (.*) \^\^\^\^')
        pkgTestResultRe = re.compile('.*---> test ([^ ]+) (had ERRORS|succeeded)')

        pkgStartRe = re.compile("^>> Entering Package (.*)")
        pkgEndRe   = re.compile("^>> Leaving Package (.*)")
        
        infoPkg = {}
        pkgSubsysMap = {}
        subsysPkgMap = {}
        
        lf = open(logFile,'r')

        startTime = time.time()
        nLines = 0
        testNames = {}
        testLines = {}
        pkgLines  = {}
        results   = {}
        pkgTests  = {}
        
        actPkg   = "None"
        actTest  = "None"
        actTstLines = 0
        actPkgLines = 0
        for line in lf:
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
            
            pkgEndMatch   = pkgEndRe.match(line)
            if pkgEndMatch:
                pkg = pkgEndMatch.group(1)
                if actPkg != pkg :
                    self.outFile.write( "pkgEndMatch> package mismatch: pkg found "+pkg+' actPkg='+actPkg+'\n')
                pkgLines[pkg] = actPkgLines

            pkgTestResultMatch= pkgTestResultRe.match(line)
            if pkgTestResultMatch :  # this seems to only appear if there is an ERROR
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
                    results[actTest] = "succeeded" # set the default, no error seen yet
            
            pkgTestEndMatch   = pkgTestEndRe.match(line)
            if pkgTestEndMatch:
                tst = pkgTestEndMatch.group(1)
                if actTest != tst :
                    self.outFile.write( "pkgTestEndMatch> package mismatch: pkg found "+pkg+' actPkg='+actPkg+'\n')
                testLines[tst] = actTstLines

        stopTime = time.time()
        lf.close()
    
        self.outFile.write( "found a total of "+ str(nLines)+ ' lines in logfile.\n')
        self.outFile.write( "analysis took "+str(stopTime-startTime)+ ' sec.\n')

        self.outFile.write( "total number of tests: " +str( len(list(results.keys())) ) + '\n')
        nMax = 1000
        self.outFile.write( "tests with more than " +str(nMax) + " lines of logs:\n")
        for pkg, lines in testLines.items():
            if lines > nMax : self.outFile.write( "  "+ pkg+ ' : ' + str(lines) +'\n')

        self.outFile.write( "Number of tests for packages: \n" )
        noTests = 0
        nrTests = 0
        indent = '    '
        totalOK = 0
        totalFail = 0
        for pkg, nTst in pkgTests.items():
            if nTst == 0:
                noTests += 1
            else:
                nrTests += 1
                if self.verbose: self.outFile.write( '-'*80 +'\n' )
                self.outFile.write( indent+pkg+' : ' )
                nOK = 0
                if self.verbose: self.outFile.write( "\n" )
                for tNam in testNames[pkg]:
                    if results[tNam] == "succeeded":
                        nOK += 1
                        totalOK += 1
                    else:
                        totalFail += 1
                    if self.verbose :
                        self.outFile.write( indent*2 + tNam +' '+ results[tNam] + '\n')
                if self.verbose: self.outFile.write( indent+ pkg+" : ")
                self.outFile.write( indent + str(len(testNames[pkg]) ) + ' tests in total,  OK:'+str(nOK)+ ' fail:'+str(len(testNames[pkg])-nOK) +'\n')
                
        self.outFile.write( indent+str(nrTests)+" packages  with   tests ("+str(float(nrTests)/float(len(pkgTests.keys())) )+")\n")
        self.outFile.write( indent+str(noTests)+" packages without tests ("+str(float(noTests)/float(len(pkgTests.keys())) )+")\n")
        self.outFile.write( indent+"in total:  tests OK : "+str(totalOK)+' tests FAIL : '+str(totalFail)+'\n')
        return

# ================================================================================


def usage():
    print("usage: "+ os.path.basename(sys.argv[0])+" --logFile <logFileName> [--verbose]\n")
    return


if __name__ == "__main__" :
    import getopt
    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'hl:sv', 
                                   ['help','logFile=','scram','verbose', 'outFile='])
    except getopt.GetoptError:
        usage()
        sys.exit(-2)

    logFile  = None
    chkScram = False
    verb     = False
    outFile  = None
    
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()
            
        if o in ('-l','--logFile',):
            logFile = a

        if o in ('-s','--scram',):
            chkScram = True

        if o in ('-v','--verbose',):
            verb = True

        if o in ('-l','--outFile',):
            outFile = a

    if not logFile:
        usage()
        sys.exit(-1)
        
    tlc = TestLogChecker(outFileIn=outFile, verbIn=verb)
    if chkScram:
        tlc.checkScramWarnings(logFile, verb)
    tlc.check(logFile)

