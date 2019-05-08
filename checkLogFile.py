#!/usr/bin/env python2

from __future__ import print_function
import os, sys, re, time


class LogChecker(object):

    # --------------------------------------------------------------------------------

    def __init__(self):

        self.htmlOut = None
        self.sumLog = None
        self.logDir = os.path.join(os.getcwd(), "www")
        self.fileIndex = 0
        self.errFiles = []
        self.pkgVers = {}
        self.verbose = 1
        if not os.path.exists(self.logDir):
            os.makedirs(self.logDir)
        return

    # --------------------------------------------------------------------------------
    def setHtml(self, html):
        self.htmlOut = html
        self.verbose = 0
        return

    # --------------------------------------------------------------------------------

    def getTags(self):

        try:
            prepFile = open('nohup.out', 'r')
        except IOError:
            prepFile = open('prebuild.log', 'r')
        except IOError:
            print("no nohup.out or prebuild.log found in . ")
            raise
        lines = prepFile.readlines()
        prepFile.close()

        pkgTagRe = re.compile('Package\s*([a-zA-Z].*)\s*version\s*(.*)\s*checkout\s*(.*)')

        for line in lines:
            pkgTagMatch = pkgTagRe.match(line)
            if pkgTagMatch:
                pkg = pkgTagMatch.group(1).strip()
                vers = pkgTagMatch.group(2).strip()
                stat = pkgTagMatch.group(3).strip()
                self.pkgVers[pkg] = vers
                if stat.lower() != "successful":
                    print("WARNING: problems checking out ", pkg, vers, stat, "(" + line + ')')

        # print "found ", str(len(self.pkgVers.keys())), 'tags'
        # for key, val in self.pkgVers.items():
        #     print "'"+key+"' " + val

        return

    # --------------------------------------------------------------------------------

    def checkLog(self, logFileName):

        here = os.getcwd()
        plat = os.environ['SCRAM_ARCH']
        pkgName = ""
        import re
        gmakeCompRe = re.compile("gmake:.*/" + plat + "/src/([a-zA-Z].*)/([a-zA-Z].*)/src/([a-zA-Z].*)\.o.*")
        gmakeTestRe = re.compile("gmake:.*/" + plat + "/src/([a-zA-Z].*)/([a-zA-Z].*)/test/([a-zA-Z].*)\.o.*")
        gmakeLinkRe = re.compile("gmake:.*/" + plat + "/src/([a-zA-Z].*)/([a-zA-Z].*)/(lib[a-zA-Z].*\.so).*")
        gmakeGeneric = re.compile("gmake:.*")

        self.fileIndex += 1

        print("\n================================================================================")
        print("in :", os.getcwd())
        print("checking file ", logFileName)
        print("================================================================================\n")
        htmlFileName = logFileName.replace('/', '_').replace(".", '-') + ".html"
        if (self.htmlOut and self.sumLog):
            self.sumLog.write(
                '<image src="http://cern.ch/pfeiffer/aaLibrarian/colline.gif" width="90%" height="3"></image>\n')
            self.sumLog.write('<h3>Checking <a href="' + htmlFileName + '">log file ' + logFileName + '</a></h3>\n')
            self.sumLog.write('\n')
            self.sumLog.write("<p>\n")

        self.getTags()

        # analyze log file

        logFile = open(logFileName, "r")
        lines = logFile.readlines()
        logFile.close()

        if len(lines) < 200:
            if (self.htmlOut and self.sumLog):
                self.sumLog.write('<font color="#ff0000"><b>Warning:</b> suspiciously short log file!</font>\n')

        nErr = 0
        nWarn = 0
        errorList = {}
        errorList['make'] = []

        subSysCompErr = {}
        subSysTestErr = {}
        subSysLinkErr = {}
        subSysGenErr = {}

        index = -1
        for line in lines:
            index += 1

            errFound = False
            mMk = gmakeCompRe.match(line)
            if mMk:
                errFound = True
                nErr += 1
                subsys = mMk.group(1)
                pkg = mMk.group(2)
                fileName = mMk.group(3)
                #                print "error found for ", subsys, pkg, ":\n     ", line
                errorList["make"].append(index)
                if subsys in subSysCompErr:
                    subSysCompErr[subsys].append((pkg, fileName, index, line))
                else:
                    subSysCompErr[subsys] = [(pkg, fileName, index, line)]

            mMk = gmakeTestRe.match(line)
            if mMk:
                errFound = True
                nErr += 1
                subsys = mMk.group(1)
                pkg = mMk.group(2)
                fileName = mMk.group(3)
                #                print "error found for ", subsys, pkg, ":\n     ", line
                errorList["make"].append(index)
                if subsys in subSysTestErr:
                    subSysTestErr[subsys].append((pkg, fileName, index, line))
                else:
                    subSysTestErr[subsys] = [(pkg, fileName, index, line)]

            mMk = gmakeLinkRe.match(line)
            if mMk:
                errFound = True
                nErr += 1
                subsys = mMk.group(1)
                pkg = mMk.group(2)
                libName = mMk.group(3)
                #                print "error found for ", subsys, pkg, ":\n     ", line
                errorList["make"].append(index)
                if subsys in subSysLinkErr:
                    subSysLinkErr[subsys].append((pkg, libName, index, line))
                else:
                    subSysLinkErr[subsys] = [(pkg, libName, index, line)]

            if not errFound:  # no specific error was found, check generic
                mMk = gmakeGeneric.match(line)
                if mMk:
                    errFound = True
                    nErr += 1
                    subsys = "unknown"
                    pkg = "unknown"
                    libName = "unknown"
                    #                    print "UNKNOWN error found for ", subsys, pkg, ":\n     ", line
                    errorList["make"].append(index)
                    if subsys in subSysGenErr:
                        subSysGenErr[subsys].append((pkg, libName, index, line))
                    else:
                        subSysGenErr[subsys] = [(pkg, libName, index, line)]

        print("--------------------------------------------------------------------------------")
        nCompErr = 0
        compErrPkg = []
        for key, val in subSysCompErr.items():
            print(str(len(val)) + " ERRORs building lib found for subsystem", key)
            for item in val:
                if item[0] not in compErrPkg:
                    compErrPkg.append(item[0])
                startIndex = len(key) + len(item[0]) + 1
                print("      " + item[0] + ' (' + str(item[1])[startIndex:] + ')')
        print("--------------------------------------------------------------------------------")
        nTestErr = 0
        testErrPkg = []
        for key, val in subSysTestErr.items():
            print(str(len(val)) + " ERRORs building tests found for subsystem", key)
            for item in val:
                if item[0] not in testErrPkg:
                    testErrPkg.append(item[0])
                print("      " + item[0] + ' (' + str(item[1]) + ')')
        print("--------------------------------------------------------------------------------")
        nLinkErr = 0
        for key, val in subSysLinkErr.items():

            subSys = key.split("/")[0]
            if ((subSys not in subSysCompErr.keys()) and
                    (subSys not in subSysTestErr.keys())):
                nLinkErr += 1
                print(str(len(val)) + " ERRORs in link-step found for subsystem", subSys)
                for item in val:
                    print("      " + item[0] + ' (' + str(item[1]) + ')')
        print("--------------------------------------------------------------------------------")
        nGenErr = 0
        genErrPkg = []
        for key, val in list(subSysGenErr.items()):
            print(str(len(val)) + " UNKNOWN ERRORs found ")
            for item in val:
                if item[0] not in genErrPkg:
                    genErrPkg.append(item[0])
                print("      " + item[0] + ' (' + str(item[3]) + ')')
        print("--------------------------------------------------------------------------------")
        print("\nA total of ", len(compErrPkg), " packages failed compilation.")
        print("\nA total of ", len(testErrPkg), " packages failed compiling tetsts.")
        print("\nA total of ", nLinkErr, " packages failed linking(only).")
        print("\nA total of ", len(genErrPkg), " unknown  errors.")
        print("\n")

        # file analyzed, now prepreare printout

        if self.htmlOut:
            errLines = []
            for key, value in errorList.items():
                for i in value:
                    if i not in errLines:
                        errLines.append(int(i))

            try:
                htmlFile = open(os.path.join(self.logDir, htmlFileName), 'w')
            except IOError:
                print("ERROR opening htmlFile ", os.path.join(self.logDir, htmlFileName))
                raise

            htmlFile.write("<html>\n<head><title>LogCheck for " + logFileName + "</title></head>\n<body>\n")
            htmlFile.write("<h1>LogCheck for " + logFileName + "</h1>\n")
            htmlFile.write("<h2>Analysis from " + time.asctime() + "</h2>\n")

            for key, val in subSysCompErr.items():
                htmlFile.write('<p>\n')
                htmlFile.write('<a href="' + htmlFileName + '#' + key + '">' + str(
                    len(val)) + ' Compile ERRORs found for subsystem ' + key)
                htmlFile.write('</a> <br />\n')
                htmlFile.write('</p>\n')

            for key, val in subSysLinkErr.items():
                htmlFile.write('<p>\n')
                htmlFile.write('<a href="' + htmlFileName + '#' + key + '">' + str(
                    len(val)) + ' Linker ERRORs found for subsystem ' + key)
                htmlFile.write('</a> <br />\n')
                htmlFile.write('</p>\n')

            for key, val in subSysCompErr.items():
                htmlFile.write('<p>\n')
                htmlFile.write('<a name=' + key + '>\n')
                htmlFile.write(str(len(val)) + ' ERRORs found for subsystem ' + key + '<br />\n')
                htmlFile.write('<ol>\n')
                for item in val:
                    pkg = item[0]
                    try:
                        htmlFile.write('<li>package ' + pkg + ' file ' + item[1] + ' Tag: ' + self.pkgVers[
                            key + "/" + pkg] + ' <br />\n')
                    except KeyError:
                        htmlFile.write('<li>package ' + pkg + ' file ' + item[1] + ' Tag: <unknown> ??? <br />\n')
                    index = item[2]
                    htmlFile.write('<a href="' + htmlFileName + '#line_' + str(index) + '">\n')
                    htmlFile.write('<pre>\n')
                    try:
                        for delta in range(-5, 1):
                            if (self.htmlOut):
                                htmlFile.write(str(index + delta) + " : " + lines[index + delta])
                            # print " ", index+delta, ":", lines[index+delta],                            
                    except IndexError:
                        pass
                    htmlFile.write('</pre>\n')
                    htmlFile.write('</a></li>\n')
                    htmlFile.write("<hr />\n")
                htmlFile.write('</ol>\n')
                htmlFile.write('</p>\n')

            for key, val in subSysGenErr.items():
                htmlFile.write('<p>\n')
                htmlFile.write(
                    '<a href="' + htmlFileName + '#' + key + '">' + str(len(val)) + ' UNKNOWN ERRORs found ')
                htmlFile.write('</a> <br />\n')
                htmlFile.write('</p>\n')

            htmlFile.write('<pre>\n')
            for index in range(len(lines)):
                # html-ify:
                line = lines[index]
                line = line.replace("&", "&amp;")
                line = line.replace("<", "&lt;")
                line = line.replace(">", "&gt;")

                if index in errLines:
                    htmlFile.write('<a name="line_' + str(index) + '">')
                    htmlFile.write('<font color="red" size+=3><b>\n')
                    htmlFile.write(line)
                    htmlFile.write('</b></font>')
                    htmlFile.write('</a> \n')
                else:
                    htmlFile.write(line)
            htmlFile.write("</pre>\n</body>\n</html>")
            htmlFile.close()

            print("\nhtml-ified log file created at:", htmlFileName, " (in", self.logDir, ")\n")

        # check if we have too many errors ....

        errLimit = False
        if len(errorList.items()) > 500:
            if (self.htmlOut and self.sumLog):
                self.sumLog.write(
                    '<font color="#ff0000"><b>Caution:</b> Too many errors found ("+len(errorList.items())+"), printout suppressed !!</font>\n')
                errLimit = True

        if self.verbose > 0 and not errLimit:
            for key, value in errorList.items():
                print("++++++++++", key)
                for index in value:
                    if (self.htmlOut and self.sumLog):
                        self.sumLog.write('<a name="' + pkgName + '"></a>\n')
                        self.sumLog.write("<hr />\n")
                        self.sumLog.write('<a href="file' + str(self.fileIndex) + '.html#line_' + str(index) + '">\n')
                    try:
                        print("------------------------------------------")
                        for delta in range(-2, 2):
                            if (self.htmlOut and self.sumLog):
                                self.sumLog.write(str(index + delta) + " : " + lines[index + delta])
                            print(" ", index + delta, ":", lines[index + delta], end=' ')
                    except IndexError:
                        pass
                    if (self.htmlOut and self.sumLog):
                        self.sumLog.write('</a>\n')

        msg = "In total: "
        if (nErr == 0):
            msg += "no errors, "
        else:
            msg += str(nErr) + " errors, "
            self.errFiles.append(pkgName)

        if (nWarn == 0):
            msg += "no warnings"
        else:
            msg += str(nWarn) + " warnings"

        msg += " found in " + str(len(lines)) + " lines."

        print(msg)
        if (self.htmlOut and self.sumLog):
            self.sumLog.write(msg + "\n")
            self.sumLog.write('</p>\n')

        return nErr, nWarn

    # --------------------------------------------------------------------------------

    def checkFiles(self, fileList=[]):

        print("going to check ", len(fileList), ' files:', fileList)

        import socket
        hostName = socket.gethostname().lower()

        import time
        date = time.ctime()

        if self.htmlOut and not self.sumLog:
            self.sumLog = open(os.path.join(self.logDir, "CheckLog-summary.html"), 'w')
            self.sumLog.write("<html>\n<head><title>Summary of logfiles</title></head>\n<body>\n<pre>\n")
            self.sumLog.write('<h2>Check of logfiles</h2>\n')
            self.sumLog.write("<p>\n")
            self.sumLog.write("Checking done on " + hostName + " at " + date)
            self.sumLog.write("</p>\n")
            self.sumLog.write("<p>\n")
            self.sumLog.write('<a href="#summary">Summary of checks</a>\n')
            self.sumLog.write("</p>\n")

        totErr = 0
        totWarn = 0

        errFiles = []

        nFiles = 0
        nFilErr = 0
        nFilWarn = 0
        for fileName in fileList:
            file = fileName
            if fileName[:2] == './':
                file = fileName[2:]
            try:
                nErr, nWarn = self.checkLog(file)
            except IOError:
                print(" IOError found !?!? ")
                raise
            nFiles += 1
            totErr += nErr
            totWarn += nWarn

            if nErr > 0: nFilErr += 1
            if nWarn > 0: nFilWarn += 1

        print("\n================================================================================\n")

        if nFiles > 0:
            print("Checked a total of ", nFiles, "log files.")
            print("A total of ", totErr, "errors in ", nFilErr, 'files.')
            print("A total of ", totWarn, "warnings in ", nFilWarn, 'files.')
        #            print "Files with errors: "
        #            for f in self.errFiles:
        #                print "\t", f
        #            print
        else:
            print("No files found to check")
            print("")

        if self.htmlOut and self.sumLog:
            self.sumLog.write('<a name="summary"></a><hr />\n')
            self.sumLog.write("Checked a total of " + str(nFiles) + " log files.\n")
            self.sumLog.write("A total of " + str(totErr) + " errors in " + str(nFilErr) + ' files.\n')
            self.sumLog.write("A total of " + str(totWarn) + " warnings in " + str(nFilWarn) + ' files.\n')
            self.sumLog.write("Files with errors: \n")

            self.sumLog.write("<table>\n")
            for f in self.errFiles:
                self.sumLog.write('<tr><td><a href="#' + f + '">' + f + '</a> </td></tr>\n')
            self.sumLog.write("</table>\n")

            self.sumLog.write("\n")
            self.sumLog.write("</pre>\n</body>\n</html>")
            self.sumLog.close()

        return


# --------------------------------------------------------------------------------

def usage():
    print(sys.argv[0], "[--hmtl] <logFile> [<logFile> ...]")

    return


# ================================================================================

if __name__ == "__main__":

    import getopt

    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'h',
                                   ['help', 'html', 'verbose='])
    except getopt.GetoptError:
        usage()
        sys.exit(-2)

    html = None
    verb = 0

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

        if o in ('--html',):
            html = True
        if o in ('--verbose',):
            verb = a

    checker = LogChecker()

    if html: checker.setHtml(html)

    checker.verbose = verb

    files = args
    checker.checkFiles(files)
