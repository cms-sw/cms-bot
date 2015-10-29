#!/usr/bin/env python
 
import os
from cmsutils import doCmd, getIBReleaseInfo

class LogUpdater():

    def __init__(self, dirIn=None, dryRun=False, remote="cmsbuild@cmssdt01.cern.ch", webDir="/data/sdt/buildlogs/"):
        self.dryRun = dryRun
        self.remote = remote
        self.cmsswBuildDir = dirIn
        rel = os.path.basename(dirIn)
        self.release = rel
        rc, day, hour = getIBReleaseInfo (rel)
        self.webTargetDir = webDir+"/"+os.environ["SCRAM_ARCH"]+"/www/"+day+"/"+rc+"-"+day+"-"+hour+"/"+self.release
        return

    def updateUnitTestLogs(self):
        
        print "\n--> going to copy unit test logs to", self.webTargetDir, '... \n'
        # copy back the test and relval logs to the install area
        # check size first ... sometimes the log _grows_ to tens of GB !!
        testLogs = ['unitTestLogs.zip','unitTests-summary.log','unitTestResults.pkl']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir)
	return

    def updateGeomTestLogs(self):
        print "\n--> going to copy Geom test logs to", self.webTargetDir, '... \n'
        testLogs = ['dddreport.log', 'domcount.log']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir)
            self.copyLogs(tl, '.', os.path.join( self.webTargetDir, 'testLogs'))
        return

    def updateDupDictTestLogs(self):
        print "\n--> going to copy dup dict test logs to", self.webTargetDir, '... \n'
        testLogs = ['dupDict-*.log']
        for tl in testLogs:
            self.copyLogs(tl, '.', self.webTargetDir)
            self.copyLogs(tl, '.', os.path.join( self.webTargetDir, 'testLogs'))
        return

    def updateLogFile(self,fileIn,subTrgDir=None):
        desdir =  self.webTargetDir
        if subTrgDir: desdir = os.path.join(desdir, subTrgDir)
        print "\n--> going to copy "+fileIn+" log to ", desdir, '... \n'
        self.copyLogs(fileIn,'.', desdir)
        return

    def updateCodeRulesCheckerLogs(self):
        print "\n--> going to copy cms code rules logs to", self.webTargetDir, '... \n'
        self.copyLogs('codeRules', '.',self.webTargetDir)
        return

    def updateRelValMatrixPartialLogs(self, partialSubDir, dirToSend):
        destination = os.path.join(self.webTargetDir,'pyRelValPartialLogs') 
        print "\n--> going to copy pyrelval partial matrix logs to", destination, '... \n'
        self.copyLogs(dirToSend, partialSubDir, destination)
        return

    def updateAddOnTestsLogs(self):
        print "\n--> going to copy addOn logs to", self.webTargetDir, '... \n'
        self.copyLogs('addOnTests.log' ,'.',self.webTargetDir)
        self.copyLogs('addOnTests.zip' ,'addOnTests/logs',self.webTargetDir)
        self.copyLogs('addOnTests.pkl' ,'addOnTests/logs',os.path.join(self.webTargetDir, 'addOnTests/logs'))
        return

    def updateIgnominyLogs(self):
        print "\n--> going to copy ignominy logs to", self.webTargetDir, '... \n'
        testLogs = ['dependencies.txt.gz','products.txt.gz','logwarnings.gz','metrics']
        for tl in testLogs:
            self.copyLogs(tl, 'igRun', os.path.join( self.webTargetDir, 'igRun'))
        return

    def updateProductionRelValLogs(self,workFlows):
        print "\n--> going to copy Production RelVals logs to", self.webTargetDir, '... \n'
        wwwProdDir = os.path.join( self.webTargetDir, 'prodRelVal')
        self.copyLogs('prodRelVal.log' ,'.',wwwProdDir)
        for wf in workFlows:
            self.copyLogs('timingInfo.txt' ,'prodRelVal/wf/'+wf,os.path.join( wwwProdDir,'wf', wf))
        return

    def updateBuildSetLogs(self,appType='fwlite'):
        print "\n--> going to copy BuildSet logs to", self.webTargetDir, '... \n'
        wwwBSDir = os.path.join( self.webTargetDir, 'BuildSet')
        self.copyLogs(appType ,'BuildSet',wwwBSDir)
        return

    def copyLogs(self, what, logSubDir, tgtDirIn):
        fromFile = os.path.join(self.cmsswBuildDir, logSubDir, what)
        ssh_opt="-o CheckHostIP=no -o ConnectTimeout=60 -o ConnectionAttempts=5 -o StrictHostKeyChecking=no -o BatchMode=yes -o PasswordAuthentication=no"
        cmd ="ssh -Y "+ssh_opt+" "+self.remote+" mkdir -p "+tgtDirIn+"; echo scp "+ssh_opt+" -r "+fromFile+" "+self.remote+":"+tgtDirIn+"/"
        try:
            if self.dryRun:
              print "CMD>>",cmd
            else:
              doCmd(cmd)
        except Exception, e:
            print "Ignoring exception during copyLogs:", str(e)
            pass
        return

