#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function

import glob
import os
import platform
import sys
import traceback
from threading import Thread

from _py2with3compatibility import run_cmd

try:
    scriptPath = os.path.dirname(os.path.abspath(__file__))
except NameError:  # __file__ not defined in interactive mode
    scriptPath = os.path.dirname(os.path.abspath(sys.argv[0]))

if scriptPath not in sys.path:
    sys.path.append(scriptPath)
sys.path.append(os.path.join(scriptPath,"python"))

from cmsutils import doCmd, MachineCPUCount, getHostName

if MachineCPUCount <= 0:
    MachineCPUCount = 2


# ================================================================================
def runCmd(cmd):
    cmd = cmd.rstrip(';')
    print("Running cmd> ", cmd)
    ret, out = run_cmd(cmd)
    if out:
        print(out)
    return ret


class IBThreadBase(Thread):
    def __init__(self, deps=None):
        if deps is None:
            deps = []

        Thread.__init__(self)
        self.deps = deps
        return

    def run(self):
        for dep in self.deps:
            if dep:
                dep.join()
        return


# ================================================================================
class UnitTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None, xType=""):
        if deps is None:
            deps = []

        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        self.xType = xType
        return

    # --------------------------------------------------------------------------------
    def checkTestLogs(self):
        # noinspection PyBroadException
        try:
            self.checkUnitTestLog()
        except Exception:
            pass
        try:
            self.splitUnitTestLogs()
        except Exception as e:
            traceback.print_exc()
            print("ERROR splitting unit test logs :", str(e))
        return

    # --------------------------------------------------------------------------------
    def checkUnitTestLog(self):
        import checkTestLog
        print("unitTest>Going to check log file from unit-tests in ", self.startDir)
        # noinspection PyBroadException
        try:
            runCmd("rm -rf " + self.startDir + "/unitTestLogs")
        except Exception:
            pass
        tlc = checkTestLog.TestLogChecker(self.startDir + "/unitTests-summary.log", True)
        tlc.check(self.startDir + "/unitTests.log")
        return

    # --------------------------------------------------------------------------------
    def splitUnitTestLogs(self):
        import splitUnitTestLog
        print("unitTest>Going to split log file from unit-tests in ", self.startDir)
        tls = splitUnitTestLog.LogSplitter(self.startDir + "/unitTests-summary.log", True)
        tls.split(self.startDir + "/unitTests.log")
        runCmd('cd ' + self.startDir + '; zip -r unitTestLogs.zip unitTestLogs')
        return

    # --------------------------------------------------------------------------------
    def run(self):
        IBThreadBase.run(self)
        arch = os.environ['SCRAM_ARCH']
        if platform.system() == 'Darwin':
            print('unitTest> Skipping unit tests for MacOS')
            return
        precmd=""
        if (self.xType == 'GPU') or ("_GPU_X" in os.environ["CMSSW_VERSION"]):
            precmd="export USER_UNIT_TESTS=cuda ;"
        skiptests = ""
        if 'lxplus' in getHostName():
            skiptests = 'SKIP_UNITTESTS=ExpressionEvaluatorUnitTest'
        TEST_PATH = os.environ['CMSSW_RELEASE_BASE'] + "/test/" + arch
        err, cmd = run_cmd(
            "cd " + self.startDir + ";scram tool info cmssw 2>&1 | grep CMSSW_BASE= | sed 's|^CMSSW_BASE=||'")
        if cmd:
            TEST_PATH = TEST_PATH + ":" + cmd + "/test/" + arch
        try:
            cmd = precmd+"cd " + self.startDir + r"; touch nodelete.root nodelete.txt nodelete.log;  sed -i -e 's|testing.log; *$(CMD_rm)  *-f  *$($(1)_objdir)/testing.log;|testing.log;|;s|test $(1) had ERRORS\") *\&\&|test $(1) had ERRORS\" >> $($(1)_objdir)/testing.log) \&\&|' config/SCRAM/GMake/Makefile.rules; "
            cmd += 'PATH=' + TEST_PATH + ':$PATH scram b -f -k -j ' + str(
                MachineCPUCount) + ' unittests ' + skiptests + ' >unitTests1.log 2>&1 ; '
            cmd += 'touch nodelete.done; ls -l nodelete.*'
            print('unitTest> Going to run ' + cmd)
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running unit-tests: cmd returned " + str(ret))
        except Exception as e:
            print("ERROR during runtests : caught exception: " + str(e))
            pass
        # noinspection PyBroadException
        try:
            testLog = self.startDir + '/tmp/' + arch + '/src/'
            logFile = self.startDir + '/unitTests.log'
            runCmd('rm -f %s; touch %s' % (logFile, logFile))
            for packDir in glob.glob(testLog + '*/*'):
                pack = packDir.replace(testLog, '')
                runCmd("echo '>> Entering Package %s' >> %s" % (pack, logFile))
                packDir += '/test'
                if os.path.exists(packDir):
                    err, testFiles = run_cmd('find ' + packDir + ' -maxdepth 2 -mindepth 2 -name testing.log -type f')
                    for lFile in testFiles.strip().split('\n'):
                        if lFile:
                            runCmd("cat %s >> %s" % (lFile, logFile))
                runCmd("echo '>> Leaving Package %s' >> %s" % (pack, logFile))
                runCmd("echo '>> Tests for package %s ran.' >> %s" % (pack, logFile))
        except Exception:
            pass
        self.checkTestLogs()
        self.logger.updateUnitTestLogs(self.xType)
        return


# ================================================================================

class LibDepsTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None):
        if deps is None:
            deps = []

        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd ' + self.startDir + ' ; ' + scriptPath + '/checkLibDeps.py -d ' + os.environ[
            "CMSSW_RELEASE_BASE"] + ' --plat ' + os.environ['SCRAM_ARCH'] + ' > chkLibDeps.log 2>&1'
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running lib dependency check: cmd returned " + str(ret))
        except Exception as e:
            print("ERROR during lib dependency check : caught exception: " + str(e))
            print("      cmd as of now   : '" + cmd + "'")

        self.logger.updateLogFile("chkLibDeps.log")
        self.logger.updateLogFile("libchk.pkl", 'new')
        return


# ================================================================================

class DirSizeTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None):
        if deps is None:
            deps = []

        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd ' + self.startDir + '; ' + scriptPath + '/checkDirSizes.py '
        ret = runCmd(cmd)
        if ret != 0:
            print("ERROR when running DirSizeTester: cmd returned " + str(ret))

        cmd = 'cd ' + self.startDir + '; storeTreeInfo.py --checkDir src --outFile treeInfo-IBsrc.json '
        ret = runCmd(cmd)
        if ret != 0:
            print("ERROR when running DirSizeTester: cmd returned " + str(ret))

        self.logger.updateLogFile(self.startDir + "/dirSizeInfo.pkl", "testLogs")
        self.logger.updateLogFile(self.startDir + "/treeInfo-IBsrc.json", "testLogs")


# ================================================================================

class ReleaseProductsDump(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None):
        IBThreadBase.__init__(self, deps)

        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        logDir = os.path.join(self.startDir, 'logs', os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir):
            os.makedirs(logDir)

        rperrFileName = os.path.join(logDir, 'relProducts.err')

        cmd = 'cd ' + self.startDir + '; RelProducts.pl > ReleaseProducts.list  2> ' + rperrFileName
        ret = runCmd(cmd)
        if ret != 0:
            print("ERROR when running ReleaseProductsChecks: cmd returned " + str(ret))
        self.logger.updateLogFile(self.startDir + "/ReleaseProducts.list")
        self.logger.updateLogFile(rperrFileName, "logs/" + os.environ['SCRAM_ARCH'])


# ================================================================================

class BuildFileDependencyCheck(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        logDir = os.path.join(self.startDir, 'logs', os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        dverrFileName = os.path.join(logDir, 'depsViolations.err')

        depDir = os.path.join(self.startDir, 'etc/dependencies')
        if not os.path.exists(depDir):
            os.makedirs(depDir)
        depFile = os.path.join(depDir, 'depsViolations.txt')

        cmd = 'cd ' + self.startDir + '; ReleaseDepsChecks.pl --detail > ' + depFile + '  2> ' + dverrFileName
        ret = runCmd(cmd)
        if ret != 0:
            print("ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret))

        cmd = 'cd ' + self.startDir + '; ' + scriptPath + '/splitDepViolationLog.py --log ' + depFile
        ret = runCmd(cmd)
        if ret != 0:
            print("ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret))

        bdir = os.path.join(depDir, "depViolationLogs")
        import fnmatch
        for root, dirnames, filenames in os.walk(bdir):
            for filename in fnmatch.filter(filenames, 'depViolation.log'):
                pkg = "/".join(root.replace(bdir, "").split('/')[1:3])
                log = os.path.join(bdir, pkg, "log.txt")
                runCmd("touch " + log + "; cat " + os.path.join(root, filename) + " >> " + log)

        self.logger.updateLogFile(self.startDir + "/depViolationSummary.pkl", "testLogs")
        self.logger.updateLogFile(dverrFileName, "logs/" + os.environ['SCRAM_ARCH'])
        self.logger.updateLogFile(depFile, "etc/dependencies/")
        self.logger.updateLogFile(bdir, "etc/dependencies/")
        return


# ================================================================================

class CodeRulesChecker(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=None):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd ' + self.startDir + '; rm -rf  codeRules; mkdir codeRules; cd codeRules; '
        cmd += 'cmsCodeRulesChecker.py -r 1,2,3,4,5 -d ' + os.environ[
            'CMSSW_RELEASE_BASE'] + '/src -S . -html 2>&1 >CodeRulesChecker.log ;'
        cmd += "find . -name log.html -type f | xargs --no-run-if-empty sed -i -e 's|cmslxr.fnal.gov|cmssdt.cern.ch|'"
        print('CodeRulesChecker: in: ', os.getcwd())
        print(' ... going to execute:', cmd)
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running CodeRulesChecker: cmd returned " + str(ret))
        except Exception as e:
            print("ERROR during runtests : caught exception: " + str(e))
            print("      cmd as of now   : '" + cmd + "'")
            pass
        self.logger.updateCodeRulesCheckerLogs()
        return


# ================================================================================

class ReleaseTester(object):

    def __init__(self, releaseDir, dryRun=False):
        self.dryRun = dryRun
        self.plat = os.environ["SCRAM_ARCH"]
        self.appset = releaseDir + "/CMSDIST"
        self.cmsswBuildDir = releaseDir
        self.release = os.path.basename(releaseDir)
        self.relTag = self.release
        self.threadList = {}
        from cmsutils import getIBReleaseInfo
        self.relCycle, day, hour = getIBReleaseInfo(self.release)
        from logUpdater import LogUpdater
        self.logger = LogUpdater(self.cmsswBuildDir, self.dryRun)
        return

    # --------------------------------------------------------------------------------
    def getDepThreads(self, jobs=None):
        if jobs is None:
            jobs = []
        deps = []
        for job in jobs:
            if job in self.threadList and self.threadList[job]:
                deps.append(self.threadList[job])
        return deps

    # --------------------------------------------------------------------------------
    def doTest(self, only=None):
        if not self.release:
            print("ReleaseTester> ERROR: no release specified !! ")
            return

        self.runProjectInit()
        if not only or 'dirsize' in only:
            print('\n' + 80 * '-' + ' dirsize \n')
            self.threadList['dirsize'] = self.runDirSize()

        if not only or 'depViolation' in only:
            print('\n' + 80 * '-' + ' depViolation \n')
            self.threadList['depViolation'] = self.runBuildFileDeps()

        if not only or 'relProducts' in only:
            print('\n' + 80 * '-' + ' relProducts \n')
            self.threadList['relProducts'] = self.runReleaseProducts()

        if not only or 'unit' in only:
            print('\n' + 80 * '-' + ' unit \n')
            self.threadList['unit'] = self.runUnitTests()

        # We only want to explicitly run this test.
        if only and 'gpu_unit' in only:
            print('\n' + 80 * '-' + ' gpu_unit \n')
            self.threadList['gpu_unit'] = self.runUnitTests([], 'GPU')

        if not only or 'codeRules' in only:
            print('\n' + 80 * '-' + ' codeRules \n')
            self.threadList['codeRules'] = self.runCodeRulesChecker()

        if not only or 'libcheck' in only:
            print('\n' + 80 * '-' + ' libcheck\n')
            self.threadList['libcheck'] = self.checkLibDeps()

        if not only or 'pyConfigs' in only:
            print('\n' + 80 * '-' + ' pyConfigs \n')
            # noinspection PyNoneFunctionAssignment
            self.threadList['pyConfigs'] = self.checkPyConfigs()

        if not only or 'dupDict' in only:
            print('\n' + 80 * '-' + ' dupDict \n')
            # noinspection PyNoneFunctionAssignment
            self.threadList['dupDict'] = self.runDuplicateDictCheck()

        print('TestWait> waiting for tests to finish ....')
        for task in self.threadList:
            if self.threadList[task]:
                self.threadList[task].join()
        print('TestWait> Tests finished ')
        return

    # --------------------------------------------------------------------------------
    # noinspection PyUnusedLocal
    def checkPyConfigs(self, deps=None):
        print("Going to check python configs in ", os.getcwd())
        cmd = scriptPath + '/checkPyConfigs.py > chkPyConf.log 2>&1'
        doCmd(cmd, self.dryRun, self.cmsswBuildDir)
        self.logger.updateLogFile("chkPyConf.log")
        self.logger.updateLogFile("chkPyConf.log", 'testLogs')
        return None

    # --------------------------------------------------------------------------------
    def checkLibDeps(self, deps=None):
        print("libDepTests> Going to run LibDepChk ... ")
        thrd = None
        try:
            thrd = LibDepsTester(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during LibDepChk : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    # noinspection PyUnusedLocal
    def runProjectInit(self, deps=None):
        print("runProjectInit> Going regenerate scram caches ... ")
        try:
            ver = os.environ["CMSSW_VERSION"]
            url = "https://github.com/cms-sw/cmssw/archive/" + ver + ".tar.gz"
            cmd = "cd " + self.cmsswBuildDir + "; rm -rf src;"
            cmd += "(curl -k -L -o src.tar.gz " + url + " || wget -q -O src.tar.gz " + url + ");"
            cmd += "tar -xzf src.tar.gz; mv cmssw-" + ver + " src; rm -rf src.tar.gz;"
            cmd += "mv src/Geometry/TrackerSimData/data src/Geometry/TrackerSimData/data.backup;"
            cmd += "scram build -r echo_CXX"
            doCmd(cmd)
        except Exception as e:
            print("ERROR during runProjectInit: caught exception: " + str(e))
        return None

    # --------------------------------------------------------------------------------
    def runCodeRulesChecker(self, deps=None):
        if deps is None:
            deps = []
        print("runCodeRulesTests> Going to run cmsCodeRulesChecker ... ")
        thrd = None
        try:
            thrd = CodeRulesChecker(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during cmsCodeRulesChecker : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    # noinspection PyUnusedLocal
    def runDuplicateDictCheck(self, deps=None):
        print("runDuplicateDictTests> Going to run duplicateReflexLibrarySearch.py ... ")
        script = 'export USER_SCRAM_TARGET=default ; eval $(scram run -sh) ; duplicateReflexLibrarySearch.py'
        for opt in ['dup', 'lostDefs', 'edmPD']:
            cmd = script + ' --' + opt + ' 2>&1 >dupDict-' + opt + '.log'
            try:
                doCmd(cmd, self.dryRun, self.cmsswBuildDir)
            except Exception as e:
                print("ERROR during test duplicateDictCheck : caught exception: " + str(e))
            self.logger.updateDupDictTestLogs()
        return None

    # --------------------------------------------------------------------------------
    def runUnitTests(self, deps=None, xType=""):
        if deps is None:
            deps = []
        print("runTests> Going to run units tests ... ")
        thrd = None
        try:
            thrd = UnitTester(self.cmsswBuildDir, self.logger, deps, xType)
            thrd.start()
        except Exception as e:
            print("ERROR during run unittests : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runDirSize(self, deps=None):
        if deps is None:
            deps = []
        print("runTests> Going to run DirSize ... ")
        thrd = None
        try:
            thrd = DirSizeTester(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during DirSize : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runReleaseProducts(self, deps=None):
        if deps is None:
            deps = []
        print("runTests> Going to run ReleaseProducts ... ")
        thrd = None
        try:
            thrd = ReleaseProductsDump(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during ReleaseProducts : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runBuildFileDeps(self, deps=None):
        if deps is None:
            deps = []
        print("runTests> Going to run BuildFileDeps ... ")
        thrd = None
        try:
            thrd = BuildFileDependencyCheck(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during RBuildFileDeps : caught exception: " + str(e))
        return thrd


# ================================================================================

def main():
    try:
        import argparse
    except ImportError:
        import archived_argparse as argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--dryRun', default=False, action='store_true')
    parser.add_argument('--only')
    args = parser.parse_args()

    rel = os.environ.get('CMSSW_BASE')
    dryRun = args.dryRun
    if args.only is not None:
        only = args.only.split(",")
    else:
        only = None

    os.chdir(rel)
    rb = ReleaseTester(rel, dryRun)
    try:
        rb.doTest(only)
    except Exception as e:
        print("ERROR: Caught exception during doTest : " + str(e))
    return


# ================================================================================
if __name__ == "__main__":
    main()
