#!/usr/bin/env python

from __future__ import print_function
import os, sys, platform, glob
from _py2with3compatibility import run_cmd
import traceback

try:
    scriptPath = os.path.dirname(os.path.abspath(__file__))
except Exception as e:
    scriptPath = os.path.dirname(os.path.abspath(sys.argv[0]))
if scriptPath not in sys.path:
    sys.path.append(scriptPath)

from cmsutils import doCmd, MachineCPUCount, getHostName


# TODO IDE says "Unresolved reference 'ActionError'", where it is defined?

# ================================================================================
def runCmd(cmd):
    while cmd.endswith(";"): cmd = cmd[:-1]
    print("Running cmd> ", cmd)
    ret, out = run_cmd(cmd)
    if out: print(out)
    return ret


from threading import Thread


class IBThreadBase(Thread):
    def __init__(self, deps=[]):
        Thread.__init__(self)
        self.deps = deps
        return

    def run(self):
        for dep in self.deps:
            if dep: dep.join()
        return


# ================================================================================
class UnitTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[], xType=""):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        self.xType = xType
        return

    # --------------------------------------------------------------------------------
    def checkTestLogs(self):
        try:
            self.checkUnitTestLog()
        except:
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
        try:
            runCmd("rm -rf " + self.startDir + "/unitTestLogs")
        except:
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
        if platform.system() == 'Darwin':
            print('unitTest> Skipping unit tests for MacOS')
            return
        if self.xType == 'GPU':
            cmd = "cd " + self.startDir + "; scram b -f echo_cuda_USED_BY | tr ' ' '\\n' | grep '^self/' | cut -d/ -f2-3 > cuda_pkgs.txt; mv src src.full;"
            cmd = cmd + " for p in $(cat cuda_pkgs.txt); do mkdir -p src/${p} ; rsync -a src.full/${p}/ src/${p}/ ; done ; scram build -r echo_CXX"
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when getting GPU unit-tests sources: cmd returned " + str(ret))
        skiptests = ""
        if 'lxplus' in getHostName(): skiptests = 'SKIP_UNITTESTS=ExpressionEvaluatorUnitTest'
        TEST_PATH = os.environ['CMSSW_RELEASE_BASE'] + "/test/" + os.environ['SCRAM_ARCH']
        err, cmd = run_cmd(
            "cd " + self.startDir + ";scram tool info cmssw 2>&1 | grep CMSSW_BASE= | sed 's|^CMSSW_BASE=||'")
        if cmd: TEST_PATH = TEST_PATH + ":" + cmd + "/test/" + os.environ['SCRAM_ARCH']
        print(TEST_PATH)
        try:
            cmd = "cd " + self.startDir + "; touch nodelete.root nodelete.txt nodelete.log;  sed -i -e 's|testing.log; *$(CMD_rm)  *-f  *$($(1)_objdir)/testing.log;|testing.log;|;s|test $(1) had ERRORS\") *\&\&|test $(1) had ERRORS\" >> $($(1)_objdir)/testing.log) \&\&|' config/SCRAM/GMake/Makefile.rules; "
            cmd += " if which timeout 2>/dev/null; then TIMEOUT=timeout; fi ; "
            cmd += 'PATH=' + TEST_PATH + ':$PATH ${TIMEOUT+timeout 3h} scram b -f -k -j ' + str(
                MachineCPUCount) + ' unittests ' + skiptests + ' >unitTests1.log 2>&1 ; '
            cmd += 'touch nodelete.done; ls -l nodelete.*'
            print('unitTest> Going to run ' + cmd)
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running unit-tests: cmd returned " + str(ret))
        except Exception as e:
            print("ERROR during runtests : caught exception: " + str(e))
            pass
        try:
            testLog = self.startDir + '/tmp/' + os.environ['SCRAM_ARCH'] + '/src/'
            logFile = self.startDir + '/unitTests.log'
            runCmd('rm -f %s; touch %s' % (logFile, logFile))
            for packDir in glob.glob(testLog + '*/*'):
                pack = packDir.replace(testLog, '')
                runCmd("echo '>> Entering Package %s' >> %s" % (pack, logFile))
                packDir += '/test'
                if os.path.exists(packDir):
                    err, testFiles = run_cmd('find ' + packDir + ' -maxdepth 2 -mindepth 2 -name testing.log -type f')
                    for lFile in testFiles.strip().split('\n'):
                        if lFile: runCmd("cat %s >> %s" % (lFile, logFile))
                runCmd("echo '>> Leaving Package %s' >> %s" % (pack, logFile))
                runCmd("echo '>> Tests for package %s ran.' >> %s" % (pack, logFile))
        except Exception as e:
            pass
        self.checkTestLogs()
        self.logger.updateUnitTestLogs(self.xType)
        return


# ================================================================================

class IgnominyTests(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        try:
            cmd = 'cd ' + self.startDir + '; '
            cmd += 'rm -rf igRun; mkdir igRun; cd igRun;'
            cmd += 'ignominy -f -A -i -g all -j ' + str(MachineCPUCount) + ' $CMSSW_RELEASE_BASE > ignominy.log 2>&1 '
            print('Ignominy> Going to run ' + cmd)
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running Ignominy: cmd returned " + str(ret))
        except Exception as e:
            print("ERROR during ignominy : caught exception: " + str(e))
            print("      cmd as of now   : '" + cmd + "'")
            pass

        cmd = 'cd ' + self.startDir + '/igRun; gzip dependencies.txt products.txt logwarnings '
        try:
            runCmd(cmd)
        except Exception as e:
            print("ERROR during ignominy : caught exception: " + str(e))
            print("      cmd as of now   : '" + cmd + "'")
            pass
        self.logger.updateIgnominyLogs()
        cmd = 'cd ' + self.startDir + '/igRun; gunzip dependencies.txt.gz products.txt.gz logwarnings.gz ; '
        cmd += 'touch igDone'
        try:
            runCmd(cmd)
        except:
            pass
        return


# ================================================================================

class AppBuildSetTests(IBThreadBase):
    def __init__(self, startDirIn, Logger, cmsdist, deps=[], appType='fwlite'):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        self.cmsdist = cmsdist
        self.appType = appType
        self.appDir = startDirIn + '/BuildSet/' + appType
        return

    def setStatus(self, status, message):
        outFile = open(self.appDir + '/index.html', 'w')
        outFile.write("<html><head></head><body><b>" + message + "</b></body></html>\n")
        outFile.close()
        outFile = open(self.appDir + '/status', 'w')
        outFile.write(status)
        outFile.close()
        print(message)
        return

    def run(self):
        IBThreadBase.run(self)
        script = scriptPath + '/buildSetTest.py'

        logFile = self.startDir + '/' + self.appType + 'BuildSet.log'
        cmd = script + ' --release ' + self.startDir + ' --ignominy ' + self.startDir + '/igRun --cmsdist ' + self.cmsdist
        cmd += ' --application ' + self.appType + ' > ' + logFile + ' 2>&1 '
        try:
            ret = runCmd(cmd)
        except:
            pass

        if not os.path.exists(self.appDir + '/status'):
            inFile = open(logFile)
            message = ''
            for x in inFile.readlines(): message += x
            inFile.close()
            self.setStatus('error', message)

        runCmd('cat ' + logFile + ' ; cp ' + logFile + ' ' + self.appDir)
        self.logger.updateBuildSetLogs(self.appType)
        return


# ================================================================================

class LibDepsTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
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
        except:
            print("ERROR during lib dependency check : caught exception: " + str(e))
            print("      cmd as of now   : '" + cmd + "'")

        self.logger.updateLogFile("chkLibDeps.log")
        self.logger.updateLogFile("libchk.pkl", 'new')
        return


# ================================================================================

class DirSizeTester(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        cmd = 'cd ' + self.startDir + '; ' + scriptPath + '/checkDirSizes.py '
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running DirSizeTester: cmd returned " + str(ret))
        except ActionError as e:
            print("Caught ActionError when running checkDirSizes.py (platform :" + os.environ[
                'SCRAM_ARCH'] + ") : " + str(e))

        cmd = 'cd ' + self.startDir + '; storeTreeInfo.py --checkDir src --outFile treeInfo-IBsrc.json '
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running DirSizeTester: cmd returned " + str(ret))
        except ActionError as e:
            print("Caught ActionError when running storeTreeInfo.py (platform :" + os.environ[
                'SCRAM_ARCH'] + ") : " + str(e))
            pass

        self.logger.updateLogFile(self.startDir + "/dirSizeInfo.pkl", "testLogs")
        self.logger.updateLogFile(self.startDir + "/treeInfo-IBsrc.json", "testLogs")
        return


# ================================================================================

class ReleaseProductsDump(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        logDir = os.path.join(self.startDir, 'logs', os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir): os.makedirs(logDir)

        rperrFileName = os.path.join(logDir, 'relProducts.err')

        cmd = 'cd ' + self.startDir + '; RelProducts.pl > ReleaseProducts.list  2> ' + rperrFileName
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running ReleaseProductsChecks: cmd returned " + str(ret))
        except ActionError as e:
            print(
                "Caught ActionError when running RelProducts.pl (platform :" + os.environ['SCRAM_ARCH'] + ") : " + str(
                    e))
            pass
        self.logger.updateLogFile(self.startDir + "/ReleaseProducts.list")
        self.logger.updateLogFile(rperrFileName, "logs/" + os.environ['SCRAM_ARCH'])
        return


# ================================================================================

class BuildFileDependencyCheck(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        logDir = os.path.join(self.startDir, 'logs', os.environ['SCRAM_ARCH'])
        if not os.path.exists(logDir): os.makedirs(logDir)
        dverrFileName = os.path.join(logDir, 'depsViolations.err')

        depDir = os.path.join(self.startDir, 'etc/dependencies')
        if not os.path.exists(depDir): os.makedirs(depDir)
        depFile = os.path.join(depDir, 'depsViolations.txt')

        cmd = 'cd ' + self.startDir + '; ReleaseDepsChecks.pl --detail > ' + depFile + '  2> ' + dverrFileName
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret))
        except ActionError as e:
            print("Caught ActionError when running ReleaseDepsChecks.pl (platform :" + os.environ[
                'SCRAM_ARCH'] + ") : " + str(e))

        cmd = 'cd ' + self.startDir + '; ' + scriptPath + '/splitDepViolationLog.py --log ' + depFile
        try:
            ret = runCmd(cmd)
            if ret != 0:
                print("ERROR when running BuildFileDependencyCheck: cmd returned " + str(ret))
        except ActionError as e:
            print("Caught ActionError when running splitDepViolationLog.py: " + str(e))
            pass

        bdir = os.path.join(depDir, "depViolationLogs")
        try:
            import fnmatch
            for root, dirnames, filenames in os.walk(bdir):
                for filename in fnmatch.filter(filenames, 'depViolation.log'):
                    pkg = "/".join(root.replace(bdir, "").split('/')[1:3])
                    log = os.path.join(bdir, pkg, "log.txt")
                    ret = runCmd("touch " + log + "; cat " + os.path.join(root, filename) + " >> " + log)
        except ActionError as e:
            pass

        self.logger.updateLogFile(self.startDir + "/depViolationSummary.pkl", "testLogs")
        self.logger.updateLogFile(dverrFileName, "logs/" + os.environ['SCRAM_ARCH'])
        self.logger.updateLogFile(depFile, "etc/dependencies/")
        self.logger.updateLogFile(bdir, "etc/dependencies/")
        return


# ================================================================================

class CodeRulesChecker(IBThreadBase):
    def __init__(self, startDirIn, Logger, deps=[]):
        IBThreadBase.__init__(self, deps)
        self.startDir = startDirIn
        self.logger = Logger
        return

    def run(self):
        IBThreadBase.run(self)
        try:
            cmd = 'cd ' + self.startDir + '; rm -rf  codeRules; mkdir codeRules; cd codeRules; '
            cmd += 'cmsCodeRulesChecker.py -d ' + os.environ[
                'CMSSW_RELEASE_BASE'] + '/src -S . -html 2>&1 >CodeRulesChecker.log ;'
            cmd += "find . -name log.html -type f | xargs --no-run-if-empty sed -i -e 's|cmslxr.fnal.gov|cmssdt.cern.ch|'"
            print('CodeRulesChecker: in: ', os.getcwd())
            print(' ... going to execute:', cmd)
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
    def getDepThreads(self, jobs=[]):
        deps = []
        for job in jobs:
            if job in self.threadList and self.threadList[job]: deps.append(self.threadList[job])
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

        if not only or 'ignominy' in only:
            print('\n' + 80 * '-' + ' ignominy \n')
            self.threadList['ignominy'] = self.runIgnominy()

        if not only or 'fwbuildset' in only:
            print('\n' + 80 * '-' + ' FWLite BuildSet\n')
            self.threadList['fwbuildset'] = self.runFWLiteBuildSet(self.getDepThreads(['ignominy']))

        if not only or 'libcheck' in only:
            print('\n' + 80 * '-' + ' libcheck\n')
            self.threadList['libcheck'] = self.checkLibDeps()

        if not only or 'pyConfigs' in only:
            print('\n' + 80 * '-' + ' pyConfigs \n')
            self.threadList['pyConfigs'] = self.checkPyConfigs()

        if not only or 'dupDict' in only:
            print('\n' + 80 * '-' + ' dupDict \n')
            self.threadList['dupDict'] = self.runDuplicateDictCheck()

        print('TestWait> waiting for tests to finish ....')
        for task in self.threadList:
            if self.threadList[task]: self.threadList[task].join()
        print('TestWait> Tests finished ')
        return

    # --------------------------------------------------------------------------------
    def checkPyConfigs(self, deps=[]):
        print("Going to check python configs in ", os.getcwd())
        cmd = scriptPath + '/checkPyConfigs.py > chkPyConf.log 2>&1'
        try:
            doCmd(cmd, self.dryRun, self.cmsswBuildDir)
            self.logger.updateLogFile("chkPyConf.log")
            self.logger.updateLogFile("chkPyConf.log", 'testLogs')
        except:
            pass
        return None

    # --------------------------------------------------------------------------------
    def checkLibDeps(self, deps=[]):
        print("libDepTests> Going to run LibDepChk ... ")
        thrd = None
        try:
            thrd = LibDepsTester(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during LibDepChk : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runProjectInit(self, deps=[]):
        print("runProjectInit> Going regenerate scram caches ... ")
        try:
            ver = os.environ["CMSSW_VERSION"]
            cmd = "cd " + self.cmsswBuildDir + "; rm -rf src;"
            cmd += "curl -k -L -s -o src.tar.gz https://github.com/cms-sw/cmssw/archive/" + ver + ".tar.gz;"
            cmd += "tar -xzf src.tar.gz; mv cmssw-" + ver + " src; rm -rf src.tar.gz;"
            cmd += "mv src/Geometry/TrackerSimData/data src/Geometry/TrackerSimData/data.backup;"
            cmd += "scram build -r echo_CXX"
            doCmd(cmd)
        except Exception as e:
            print("ERROR during runProjectInit: caught exception: " + str(e))
        return None

    # --------------------------------------------------------------------------------
    def runCodeRulesChecker(self, deps=[]):
        print("runCodeRulesTests> Going to run cmsCodeRulesChecker ... ")
        thrd = None
        try:
            thrd = CodeRulesChecker(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during cmsCodeRulesChecker : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runDuplicateDictCheck(self, deps=[]):
        print("runDuplicateDictTests> Going to run duplicateReflexLibrarySearch.py ... ")
        script = 'duplicateReflexLibrarySearch.py'
        for opt in ['dup', 'lostDefs', 'edmPD']:
            cmd = script + ' --' + opt + ' 2>&1 >dupDict-' + opt + '.log'
            try:
                doCmd(cmd, self.dryRun, self.cmsswBuildDir)
            except Exception as e:
                print("ERROR during test duplicateDictCheck : caught exception: " + str(e))
            self.logger.updateDupDictTestLogs()
        return None

    # --------------------------------------------------------------------------------
    def runIgnominy(self, deps=[]):
        print("ignominyTests> Going to run ignominy tests ... ")
        thrd = None
        try:
            thrd = IgnominyTests(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during run ignominytests : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runFWLiteBuildSet(self, deps=[]):
        print("FWLiteBuildSet> Going to run FWLite BuildSet tests ... ")
        thd = None
        try:
            thd = AppBuildSetTests(self.cmsswBuildDir, self.logger, self.appset, deps, 'fwlite')
            thd.start()
        except Exception as e:
            print("ERROR during run FWLiteBuildSet : caught exception: " + str(e))
        return thd

    # --------------------------------------------------------------------------------
    def runUnitTests(self, deps=[], xType=""):
        print("runTests> Going to run units tests ... ")
        thrd = None
        try:
            thrd = UnitTester(self.cmsswBuildDir, self.logger, deps, xType)
            thrd.start()
        except Exception as e:
            print("ERROR during run unittests : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runDirSize(self, deps=[]):
        print("runTests> Going to run DirSize ... ")
        thrd = None
        try:
            thrd = DirSizeTester(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during DirSize : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runReleaseProducts(self, deps=[]):
        print("runTests> Going to run ReleaseProducts ... ")
        thrd = None
        try:
            thrd = ReleaseProductsDump(self.cmsswBuildDir, self.logger, deps)
            thrd.start()
        except Exception as e:
            print("ERROR during ReleaseProducts : caught exception: " + str(e))
        return thrd

    # --------------------------------------------------------------------------------
    def runBuildFileDeps(self, deps=[]):
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
    import getopt
    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'h', ['help', 'dryRun', 'only='])
    except getopt.GetoptError as msg:
        print(msg)
        sys.exit(-2)
    rel = os.environ.get('CMSSW_BASE')
    buildDir = rel
    dryRun = False
    only = None
    for o, a in opts:
        if o in ('--dryRun',): dryRun = True
        if o in ('--only',):   only = a.split(",")
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
