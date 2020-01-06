#!/usr/bin/env python
# encoding: utf-8
"""
Created by Andreas Pfeiffer on 2008-08-05.
Copyright (c) 2008 CERN. All rights reserved.
"""
from __future__ import print_function
import sys, os, re, time
import getopt

if sys.version_info[0] == 3:
    def cmp(a,b):
        return ((a > b) - (a < b))


def pkgCmp(a,b):
    if a.subsys == b.subsys: return cmp(a.pkg, b.pkg)
    else: return cmp(a.subsys, b.subsys)

# ================================================================================

class ErrorInfo(object):
    """keeps track of information for errors"""
    def __init__(self, errType, msg):
        super(ErrorInfo, self).__init__()
        self.errType = errType
        self.errMsg  = msg

# ================================================================================

class PackageInfo(object):
    """keeps track of information for each package"""
    def __init__(self, subsys, pkg):
        super(PackageInfo, self).__init__()

        self.subsys  = subsys
        self.pkg     = pkg
        self.errInfo = []
        self.errSummary = {}
        self.errLines = {}
        self.warnOnly = False
        
    def addErrInfo(self, errInfo, lineNo):
        """docstring for addErr"""
        self.warnOnly = True
        if 'Error' in errInfo.errType: self.warnOnly = False
        self.errInfo.append( errInfo )
        if errInfo.errType not in self.errSummary.keys():
            self.errSummary[errInfo.errType] = 1
        else:
            self.errSummary[errInfo.errType] += 1
        self.errLines[lineNo] = errInfo.errType
        
    def name(self):
        """docstring for name"""
        return self.subsys+'/'+self.pkg
        
# ================================================================================

class LogFileAnalyzer(object):
    """docstring for LogFileAnalyzer"""
    def __init__(self, topDirIn='.', topUrlIn='', verbose = -1, pkgsList = None, release = None):
        super(LogFileAnalyzer, self).__init__()

        self.topDir = os.path.abspath( topDirIn )

        self.topURL = topUrlIn
        if not pkgsList:  pkgsList = "../../../../../src/PackageList.cmssw"
        if self.topURL != '' :
            if self.topURL[-1] != '/' : self.topURL += '/'
            if not release: release = self.topURL.split('/')[-3]  # TODO no error catching
        self.release = release
        self.pkgsList = pkgsList
        self.verbose = verbose

        self.tagList = {}
        
        self.nErrorInfo  = {}
        self.nFailedPkgs = []
        self.packageList = []
        self.pkgOK       = []
        self.pkgErr      = []
        self.pkgWarn     = []
                
        self.errorKeys = ['dictError',
                          'compError',
                          'linkError',
                          'pythonError',
                          'compWarning',
                          'dwnlError',
                          'miscError',
                          'ignoreWarning',
                         ]

        self.styleClass = {'dictError'   : 'dictErr',
                           'compError'   : 'compErr',
                           'linkError'   : 'linkErr',
                           'pythonError' : 'pyErr',
                           'dwnlError'   : 'dwnldErr',
                           'miscError'   : 'miscErr',
                           'compWarning' : 'compWarn',
                           'ignoreWarning' : 'compWarn',
                           'ok'          : 'ok',
                           }


        # get the lists separately for "priority" treatment ...
        self.errMap = {}
        for key in self.errorKeys:
            self.errMap[key] = []

        # get the lists separately for summary accounting
        self.errMapAll = {}
        for key in self.errorKeys:
            self.errMapAll[key] = []

    def  getDevelAdmins(self):
        """
        get list of admins and developers from .admin/developers file in each package
        needed for sending out e-mails
        """
        pass
        
    def getTagList(self):

        import glob
        srcdir = os.path.dirname(self.pkgsList)+"/"
        for pkg in glob.glob(srcdir+'*/*'):
          pkg = pkg.replace(srcdir,"")
          self.tagList[pkg] = ""
        return
        
    def analyze(self):
        """loop over all packages and analyze the log files"""

        os.chdir(self.topDir)
        
        self.getTagList()

        import glob
        start = time.time()
        packageList = glob.glob('*/*/build.log')

        if self.verbose > 0: print("going to analyze ", len(packageList), 'files.')

        for logFile in packageList:
            self.analyzeFile(logFile)

        pkgDone = []
        for pkg in self.packageList:
            if pkg.warnOnly : self.pkgWarn.append(pkg)
            if pkg.errInfo:
                self.pkgErr.append(pkg)
                for key in self.errorKeys:
                    if key in pkg.errSummary.keys() :
                        self.errMapAll[key].append(pkg)
                    if key in pkg.errSummary.keys() and pkg not in pkgDone:
                        self.errMap[key].append(pkg)
                        pkgDone.append(pkg)
            else:    
                self.pkgOK.append(pkg)

        stop = time.time()
        self.anaTime = stop-start
        pass

    def report(self):
        """show collected info"""
        
        print('analyzed ', len(self.packageList), 'log files in', str(self.anaTime), 'sec.')
        totErr = 0
        for key, val in self.nErrorInfo.items():
            totErr += int(val)
            
        print('found ', totErr, ' errors and warnings in total, by type:')
        for key, val in self.nErrorInfo.items():
            print('\t', key, ' : ', val, ' in ', len(self.errMapAll[key]), 'packages')
        
        print('found ', len(self.pkgOK),  'packages without errors/warnings.')
        print('found ', len(self.pkgErr), 'packages with errors or warnings, ', len(self.pkgWarn), ' with warnings only.')
#        for pkg in pkgErr:
#            print '\t',pkg.name(), ' : ',
#            for key in ['dictError', 'compError', 'linkError']:
#                if key in pkg.errSummary.keys():
#                    print key, pkg.errSummary[key],
#                else:
#                    print key, ' N/A ',
#            print ''

## for debugging
#            for err in pkg.errInfo:
#                if err.errType == 'miscError':
#                    print '\t\t', err.errMsg
        
        start = time.time()
        self.makeHTMLSummaryPage()
        for key in self.errorKeys:
            pkgList = self.errMap[key]
            pkgList.sort()
            # print 'Error type :', key
            # print [x.name() for x in pkgList]
            for pkg in pkgList:
                self.makeHTMLLogFile(pkg)
        for pkg in self.pkgOK:
            self.makeHTMLLogFile(pkg)
        stop = time.time()
        print("creating html pages took ", str(stop-start), 'sec.')
        
    def makeHTMLSummaryPage(self):

        keyList = self.errorKeys
        
        htmlDir = '../html/'
        if not os.path.exists(htmlDir):
            os.makedirs(htmlDir)

        htmlFileName = htmlDir + "index.html"
        htmlFile = open (htmlFileName, 'w')
        htmlFile.write("<html>\n")
        htmlFile.write("<head>\n")
        htmlFile.write('<link rel="stylesheet" type="text/css" href="http://cern.ch/cms-sdt/intbld.css">\n')
        htmlFile.write("<title>Summary for build of "+self.release+"</title>")
        htmlFile.write("</head>\n")
        htmlFile.write("<body>\n")
        htmlFile.write("<h2>Summary for build of "+self.release+"</h2>\n")
        htmlFile.write("<h3>Platform: "+os.environ["SCRAM_ARCH"]+"</h3>\n")
        htmlFile.write('analyzed '+ str(len(self.packageList)) + ' log files in ' + str(self.anaTime) +' sec.\n')
        totErr = 0
        for key, val in self.nErrorInfo.items():
            totErr += int(val)
        
        htmlFile.write('<h3> found '+ str(totErr)+ ' errors and warnings in total, by type: </h3>\n')
        htmlFile.write('<table border="1" cellpadding="10">')
        htmlFile.write('<tr> <td><b>error type</b></td><td><b> # packages </b></td><td><b> total # errors </b></td></tr>\n')
        for key in keyList:
            val = 0
            try:
                val = self.nErrorInfo[key]
            except KeyError:
                pass
            nPkgE = len(self.errMapAll[key])
            htmlFile.write('<tr class="'+self.styleClass[key]+'"> <td>'+ key + ' </td><td> ' + str(nPkgE) + '</td><td> ' + str(val) + '</td></tr>\n')
        htmlFile.write('<table>')
        
        htmlFile.write('<table border="1">\n')
        htmlFile.write(" <tr>")
        htmlFile.write("<th>")
        htmlFile.write('status')
        htmlFile.write("</th>")    
        htmlFile.write("<th>")
        htmlFile.write('subsystem/package')
        htmlFile.write("</th>")    
        for key in keyList:
            htmlFile.write("<th>")
            htmlFile.write(key)
            htmlFile.write("</th>")    
        htmlFile.write(" </tr> \n")
        
        topLogString = self.topURL

        for key in keyList:
            pkgList = self.errMap[key]
            pkgList.sort(pkgCmp)
            
            for pkg in pkgList:
                if not pkg.name() in self.tagList: continue
                styleClass = 'ok'
                for cKey in self.errorKeys :
                    if styleClass == 'ok'  and cKey in pkg.errSummary.keys(): styleClass = self.styleClass[cKey]
                htmlFile.write(' <tr>')
                htmlFile.write('<td class="'+styleClass+'">&nbsp;</td>')
                htmlFile.write('<td>')
                link = ' <a href="'+topLogString+pkg.name()+'/log.html">'+pkg.name()+'   '+self.tagList[pkg.name()]+'  </a> '
                htmlFile.write(link)
                htmlFile.write("</td>")    
                for pKey in keyList:
                    htmlFile.write("<td>")
                    if pKey in pkg.errSummary.keys():
                        htmlFile.write( str(pkg.errSummary[pKey]).decode('ascii','ignore') )
                    else:
                        htmlFile.write(' - ')
                    htmlFile.write("</td>")    

                htmlFile.write("</tr>\n")    

        pkgList = self.pkgOK
        pkgList.sort(pkgCmp)
        
        for pkg in pkgList:
            htmlFile.write(' <tr>')
            htmlFile.write('<td class="ok">&nbsp;</td>')
            htmlFile.write('<td>')
            link = ' <a href="'+topLogString+pkg.name()+'/log.html">'+pkg.name()+'   '+self.tagList[pkg.name()]+'</a> '
            htmlFile.write(link)
            htmlFile.write("</td>")    
            for pKey in self.errorKeys:
                htmlFile.write("<td>")
                htmlFile.write(' - ')
                htmlFile.write("</td>")    
            htmlFile.write("</tr>\n")    

        htmlFile.write("</table>\n")    
        htmlFile.write("</body>\n")    
        htmlFile.write("</html>\n")        

        htmlFile.close()

        # write out all info also as pkl files so we can re-use it:
        from pickle import Pickler
        summFile = open(htmlDir+'/'+'logAnalysis.pkl','wb')
        pklr = Pickler(summFile, protocol=2)
        pklr.dump([self.release,os.environ["SCRAM_ARCH"], self.anaTime])
        pklr.dump(self.errorKeys)
        pklr.dump(self.nErrorInfo)
        pklr.dump(self.errMapAll)
        pklr.dump(self.packageList)
        pklr.dump(self.topURL)
        pklr.dump(self.errMap)
        pklr.dump(self.tagList)
        pklr.dump(self.pkgOK)
        summFile.close()

        return
        
    def makeHTMLLogFile(self, pkg):
        """docstring for makeHTMLFile"""

        htmlDir = '../html/'+pkg.name()+'/'
        if not os.path.exists(htmlDir):
            os.makedirs(htmlDir)
        htmlFileName = htmlDir +'log.html'    

        logFileName = pkg.name()+'/build.log'
        logFile = open(logFileName, 'r')
        htmlFile = open (htmlFileName, 'w')
        htmlFile.write("<html>\n")
        htmlFile.write("<head>\n")
        htmlFile.write('<link rel="stylesheet" type="text/css" href="http://cern.ch/cms-sdt/intbld.css">\n')
        htmlFile.write("<title>Log File for "+pkg.name()+"</title>")
        htmlFile.write("</head>\n")
        htmlFile.write("<body>\n")
        htmlFile.write("<h2>Log File for "+pkg.name()+'   '+self.tagList[pkg.name()]+"</h2>\n")
        htmlFile.write("<pre>\n")
        lineNo = -1
        for line in logFile.readlines():
            lineNo += 1
            # HTML sanitisation:
            newLine = line.replace('&','&amp;') # do this first to not escape it again in the next subs
            newLine = newLine.replace('<','&lt;').replace('>','&gt;')
            if lineNo in pkg.errLines.keys():
                newLine = '<class='+self.styleClass[pkg.errLines[lineNo]]+'> <b> '+newLine+' </b></class>'
            htmlFile.write(newLine.decode('ascii','ignore'))
        htmlFile.write("</pre>\n")    
        htmlFile.write("</body>\n")    
        htmlFile.write("</html>\n")        
        htmlFile.close()
        
    def analyzeFile(self, fileNameIn):
        """read in file and check for errors"""
        subsys, pkg, logFile = fileNameIn.split('/')

        if self.verbose > 5 : print("analyzing file : ", fileNameIn)
        
        fileIn = open(fileNameIn, 'r')
        shLib = 'so'
        if os.uname()[0] == 'Darwin' :
            shLib = 'dylib'
        errorInf =[
            {str('^.*? cannot find -l(.*?)$') : ['linkError', 'missing library "%s"']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/src/'+subsys+pkg+'/classes_rflx\.cpp')  : ['dictError', 'for package dictionary']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/src/'+subsys+pkg+'/.*?\.'+shLib)        : ['linkError', 'for package library']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/src/'+subsys+pkg+'/.*?\.o')             : ['compError', 'for package library']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/bin/(.*?)/.*?\.o')                      : ['compError', 'for executable %s']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/bin/(.*?)/\1')                          : ['linkError', 'for executable %s']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/bin/(.*?)/lib\1\.'+shLib)               : ['linkError', 'for shared library %s in bin']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/stubs/lib(.*?)\.'+shLib)           : ['linkError', 'for shared library %s in test/stubs']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/(.*?)/.*?\.'+shLib)                : ['linkError', 'for shared library %s in test']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/stubs/.*?\.o')                     : ['compError', 'for library in test/stubs']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/(.*?)/.*?\.o')                     : ['compError', 'for executable %s in test']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/(.*?)\.'+shLib)                    : ['linkError', 'for shared library %s in test']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/(.*?)\.o')                         : ['compError', 'for executable %s in test']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/(.*?)/\1')                         : ['linkError', 'for executable %s in test']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/plugins/(.*?)/.*?\.o')                  : ['compError', 'for plugin %s in plugins']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/plugins/(.*?)/lib.*?\.'+shLib)          : ['linkError', 'for plugin library %s in plugins']},
            {str('^ *\*\*\* Break \*\*\* illegal instruction')                                      : ['compError', 'Break illegal instruction']},
            {str('^AttributeError: .*')                                                             : ['pythonError', 'importing another module']},
            {str('^ImportError: .*')                                                                : ['pythonError', 'importing another module']},
            {str('^SyntaxError: .*')                                                                : ['pythonError', 'syntax error in module']},
            {str('^NameError: .*')                                                                  : ['pythonError', 'name error in module']},
            {str('^TypeError: .*')                                                                  : ['pythonError', 'type error in module']},
            {str('^ValueError: .*')                                                                 : ['pythonError', 'value error in module']},
            {str('^gmake: \*\*\* .*?/src/'+subsys+'/'+pkg+'/test/data/download\.url')               : ['dwnlError', 'for file in data/download.url in test']},
            {str('^ */.*?/'+self.release+'/src/'+subsys+'/'+pkg+'.*?\:\d*\: warning: ')             : ['compWarning', 'for file in package']},
            {str('^ */.*?/'+self.release+'/src/.*?\:\d+\: warning: ')                               : ['compWarning', 'for file in release']},
            {str('^Warning: ')                                                                      : ['compWarning', 'for file in package']},
            {str('^ */.*?/'+self.release+'/src/'+subsys+'/'+pkg+'.*?\:\d+\: error: ')               : ['compError', 'for file in package']},
            {str('^ */.*?/'+self.release+'/src/.*?\:\d+\: error: ')                                 : ['compError', 'for file in release']},
            {str('^.*?\:\d+\: error: ')                                                             : ['compError', 'for file in externals']},
            {str('^ *tmp/.*?/src/'+subsys+'/'+pkg+'/src/(.*?)/lib.*?\.'+shLib+'\: undefined reference to .*')     : ['linkError', 'for package library %s ']},
            {str('^ *tmp/.*?/src/'+subsys+'/'+pkg+'/plugins/(.*?)/lib.*?\.'+shLib+'\: undefined reference to .*') : ['linkError', 'for plugin library %s in plugins']},
            {str("^error: class '.*?' has a different checksum for ClassVersion")                   : ['compError', 'for a different checksum for ClassVersion']},
            {str('^.*: (more undefined references to|undefined reference to).*')                     : ['compError', 'Missing symbols in a package']},
          ]

        miscErrRe = re.compile('^gmake: \*\*\* (.*)$')
        genericLinkErrRe = re.compile('^gmake: \*\*\* \[tmp/.*?/lib.*?'+shLib+'\] Error 1')
        
        if ('_gcc46' in os.environ["SCRAM_ARCH"]):
            errorInf.append({str('^.*?:\d+\: warning\: ') : ['compWarning', 'from external in package']})
        else:
            errorInf.append({str('^.*?:\d+\: warning\: ') : ['ignoreWarning', 'from external in package']})
        errors = []
        for errI in errorInf:
          for err, info in errI.items():
            errors.append({re.compile(err) : info})
            
        pkgInfo = PackageInfo(subsys, pkg)
        lineNo = -1
        for line in fileIn:
            lineNo += 1
            errFound = False
            for errI in errors:
              isMatched = False
              for errRe, info in errI.items():
                errMatch = errRe.match(line)
                if errMatch:
                    errFound = True
                    isMatched = True
                    errTyp, msg = info
                    if '%s' in msg :
                        msg = info[1] % errMatch.groups(1)
                    if errTyp in self.nErrorInfo.keys():
                        self.nErrorInfo[errTyp] += 1
                    else:
                        self.nErrorInfo[errTyp] = 1    
                    pkgInfo.addErrInfo( ErrorInfo(errTyp, msg), lineNo )
                    break
              if isMatched: break
            if not errFound :
                miscErrMatch = miscErrRe.match(line)
                if miscErrMatch:
                    if not genericLinkErrRe.match(line) : 
                        errTyp = 'miscError'
                        msg = 'Unknown error found: %s' % miscErrMatch.groups(1)
                        if errTyp in self.nErrorInfo.keys():
                            self.nErrorInfo[errTyp] += 1
                        else:
                            self.nErrorInfo[errTyp] = 1    
                        pkgInfo.addErrInfo( ErrorInfo(errTyp, msg), lineNo )
                
        fileIn.close()

        self.packageList.append( pkgInfo )

        return
    
# ================================================================================

help_message = '''
     -h, --help          : print this message
     -l, --logDir  <dir> : the path to the dir with the log files to analyze
     -r, --release <name>: Release version
     -p, --pkgList <file>: Path to PackageList.cmssw file
     -t, --topURL  <url> : the base URL to use for generating the html files
     -v, --verbose <lvl> : set verbosity level, the higher the number, the more verbose printout you will get

Example:
when run in: /build/intBld/rc/wed-21/CMSSW_3_1_X_2009-07-08-2100/tmp/slc4_ia32_gcc345/cache/log/src as:
buildLogAnalyzer.py http://cern.ch/cms-sdt/rc/slc4_ia32_gcc345/www/wed/3.1-wed-21/CMSSW_3_1_X_2009-07-08-2100/new/
the script will produce the html version of the log files of the IB and write them into:
/build/intBld/rc/wed-21/CMSSW_3_1_X_2009-07-08-2100/tmp/slc4_ia32_gcc345/cache/log/html/

'''

class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


def main(argv=None):
    logDir = '.'
    topURL = './'
    verbose = -1
    pkgList = os.getenv("CMSSW_BASE",None)
    if pkgList: pkgList+="/src/PackageList.cmssw"
    rel = os.getenv("CMSSW_VERSION",None)
    if argv is None:
        argv = sys.argv

    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hv:l:t:p:r:", ["help", "verbose=", "logDir=", "topURL=", "pkgList=", "release="])
        except getopt.error as msg:
            raise Usage(msg)

        # option processing
        for option, value in opts:
            if option in ("-v", '--verbose'):
                verbose = int(value)
            if option in ("-h", "--help"):
                raise Usage(help_message)
            if option in ("-l", "--logDir"):
                logDir = value
            if option in ("-r", "--release"):
                rel = value
            if option in ("-p", "--pkgList"):
                pkgList = value
            if option in ("-t", "--topURL"):
                topURL = value

        if not topURL:
            raise Usage(help_message)

        if not os.path.exists(logDir): return

        lfa = LogFileAnalyzer(logDir, topURL, verbose, pkgList, rel)
        lfa.analyze()
        lfa.report()

    except Usage as err:
        print(sys.argv[0].split("/")[-1] + ": " + str(err.msg), file=sys.stderr)
        print("\t for help use --help", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
