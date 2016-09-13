#!/usr/bin/env python
 
import os
from cmsutils import doCmd, getIBReleaseInfo

class LogUpdater():

    def __init__(self, dirIn=None, dryRun=False, remote="cmsbuild@cmssdtprod.cern.ch", webDir="/data/sdt/buildlogs/"):
        self.dryRun = dryRun
        self.remote = remote
        self.cmsswBuildDir = dirIn
        rel = os.path.basename(dirIn)
        self.release = rel
        rc, day, hour = getIBReleaseInfo (rel)
        self.webTargetDir = webDir+"/"+os.environ["SCRAM_ARCH"]+"/www/"+day+"/"+rc+"-"+day+"-"+hour+"/"+self.release
        self.ssh_opt = "-o CheckHostIP=no -o ConnectTimeout=60 -o ConnectionAttempts=5 -o StrictHostKeyChecking=no -o BatchMode=yes -o PasswordAuthentication=no"
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
        self.runRemoteCmd("touch "+os.path.join(destination,dirToSend,"wf.done"))
        return

    def relvalAlreadyDone(self, wf):
        wfDoneFile = "wf.done"
        destination = os.path.join(self.webTargetDir,'pyRelValPartialLogs',str(wf)+"_*",wfDoneFile)
        code, out = self.runRemoteCmd ("ls -d "+destination)
        return ((code == 0) and out.endswith(wfDoneFile))
   
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
        self.runRemoteCmd("mkdir -p "+tgtDirIn)
        self.copy2Remote(os.path.join(self.cmsswBuildDir, logSubDir, what),tgtDirIn+"/")

    def runRemoteCmd(self, cmd):
        self.runRemoteHostCmd(cmd,"cmsbuild@cmssdtdev.cern.ch")
        return self.runRemoteHostCmd(cmd,self.remote)

    def copy2Remote(self, src, des):
        self.copy2RemoteHost(src,des,"cmsbuild@cmssdtdev.cern.ch")
        return self.copy2RemoteHost(src,des,self.remote)

    def runRemoteHostCmd(self, cmd, host):
        cmd ="ssh -Y "+self.ssh_opt+" "+host+" "+cmd
        try:
            if self.dryRun:
              print "CMD>>",cmd
            else:
              return doCmd(cmd)
        except Exception, e:
            print "Ignoring exception during runRemoteCmd:", str(e)
            return (1,str(e))

    def copy2RemoteHost(self, src, des, host):
        cmd ="scp "+self.ssh_opt+" -r "+src+" "+host+":"+des
        try:
            if self.dryRun:
              print "CMD>>",cmd
            else:
              return doCmd(cmd)
        except Exception, e:
            print "Ignoring exception during copy2Remote:", str(e)
            return (1,str(e))

