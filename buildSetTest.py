#!/usr/bin/env python
# TODO is this script used ?
from __future__ import print_function
import os, sys, re
from _py2with3compatibility import getstatusoutput

scriptPath = os.path.dirname(os.path.abspath(sys.argv[0]))


class AppBuildSet(object):
    def __init__(self, releaseDir, cmsdist, appType='fwlite'):
        self.startDir = releaseDir
        self.cmsdist = cmsdist
        self.appType = appType
        self.appDir = releaseDir + '/BuildSet/' + appType
        self.refFiles = {'RefAppSet': appType + '_application_set.file',
                         'RefBuildSet': appType + '_build_set.file',
                         }
        return

    def initArea(self):
        cmd = 'rm -rf ' + self.appDir + '; mkdir -p ' + self.appDir
        ret, outX = getstatusoutput(cmd)
        return

    def setStatus(self, status, message):
        if os.path.exists(self.appDir + '/status'): return
        outFile = open(self.appDir + '/index.html', 'w')
        outFile.write("<html><head></head><body><b>" + message + "</b></body></html>\n")
        outFile.close()
        outFile = open(self.appDir + '/status', 'w')
        outFile.write(status)
        outFile.close()
        print(message)
        return

    def getRefFiles(self):
        for sFile in self.refFiles:
            xFile = os.path.join(self.cmsdist, self.refFiles[sFile])
            if (not os.path.exists(xFile)) or (os.system('cp ' + xFile + ' ' + self.appDir + '/' + sFile) != 0):
                self.setStatus('error', 'ERROR: Can not find file ' + xFile)
                return False
        return True

    def run(self, ignominyDir):
        self.initArea()
        if not os.path.exists(ignominyDir + '/igDone'):
            err = self.appType + 'BuildSet> Skipping test for release, ignominy test did not run or failed'
            self.setStatus('skip', err)
            return

        if not self.getRefFiles():
            err = self.appType + 'BuildSet> Skipping test for release, There are errors in getting ref files.'
            self.setStatus('skip', err)
            return

        cmd = 'cd ' + self.startDir + '; eval `scramv1 run -sh`; cd ' + self.appDir
        for xtype in ['packages', 'tools']:
            for xsec in ['binary', 'source']:
                cmd += ' ; MakeBuildSet -f ./RefAppSet -o ' + xtype + ' -D ' + xsec + ' -d ' + ignominyDir + ' | sort > ' + xtype + '_' + xsec

        print(self.appType + 'BuildSet> Going to run ' + cmd)
        ret, outX = getstatusoutput(cmd)
        if outX: print(outX)
        if ret != 0:
            err = "ERROR when running MakeBuildSet: cmd returned " + str(ret)
            self.setStatus('error', err)
        return

    # ================================================================================

    def readPackages(self, inFile, allPackages):
        packs = {}
        if not os.path.exists(inFile): return packs
        rFile = open(inFile)
        for line in rFile.readlines():
            line = line.rstrip()
            if re.match('^\s*(#.*|)$', line): continue
            packs[line] = 1
            allPackages[line] = 1
        rFile.close()
        return packs

    def getRefApplicationSet(self, allPackages):
        return self.readPackages(self.appDir + '/RefAppSet', allPackages)

    def getRefBuildSet(self, allPackages):
        return self.readPackages(self.appDir + '/RefBuildSet', allPackages)

    def getPackageDetail(self, pack, pData):
        pinfo = [0, 0, 0, 0]
        if pack in self.AppSet: pinfo[3] = 1
        if pack in self.BldSet: pinfo[2] = 1
        index = 1
        for xsec in ['binary', 'source']:
            if pack in pData[xsec]['packages']: pinfo[index] = 1
            index -= 1
        return pinfo

    def generateHTML(self):
        if os.path.exists(self.appDir + '/status'): return
        pData = {'all': {'packages': {},
                         'tools': {},
                         },
                 }
        self.AppSet = self.getRefApplicationSet(pData['all']['packages'])
        self.BldSet = self.getRefBuildSet({})

        for xsec in ['binary', 'source']:
            pData[xsec] = {}
            for xtype in ['packages', 'tools']:
                pData[xsec][xtype] = self.readPackages(self.appDir + '/' + xtype + '_' + xsec, pData['all'][xtype])

        packs = list(pData['all']['packages'].keys())
        packs.sort()

        res = []
        for i in range(0, 6): res.append([])
        for pk in packs:
            offset = 0
            if pk in self.AppSet and pk in self.BldSet:
                res[4].append(pk)
                continue
            elif pk in self.BldSet:
                offset = 2
            if pk in pData['binary']['packages']:
                res[offset + 1].append(pk)
            else:
                res[offset].append(pk)

        packs = list(self.BldSet.keys())
        packs.sort()
        for pk in packs:
            if pk in pData['all']['packages']: continue
            res[5].append(pk)

        release = os.path.basename(self.startDir)
        outFile = open(self.appDir + '/index.html', 'w')
        inFile = open(scriptPath + '/IBPageHead.txt')
        for l in inFile.readlines(): outFile.write(l)
        inFile.close()
        outFile.write("""<a name="top">&nbsp;</a><h3> %s BuildSet Summary for %s IB on platform %s -- <a href="http://cmssdt.cern.ch/SDT/cgi-bin/showIB.py">Back to IB portal</a> </h3>
                 <table border="1"  ><thead><tr><th> <b>Packages Types</b></th><th> <b>Dependency</b></th><th> <b>Count</b> </th></tr></thead><tbody>\n""" % (
        self.appType.upper(), release, os.environ['SCRAM_ARCH']))

        rCount = []
        rStyle = []
        for i in range(0, 6): rStyle.append('class=ok1')
        for i in range(0, 6): rCount.append(len(res[i]))
        rStyle[0] = 'class=error'
        rStyle[1] = 'class=warning'
        rStyle[2] = 'class=ok3'
        rStyle[3] = 'class=ok2'
        rStyle[5] = 'class=aqua'

        outFile.write(" <tr><td %(class)s> Ref AppSet </td>     <td> N/A </td>        <td> %(count)d </td></tr>\n" % {
            'class': rStyle[4], 'count': rCount[4]})
        outFile.write(" <tr><td %(class)s> Ref BuildSet </td>   <td> Binary </td>     <td> +%(count)d </td></tr>\n" % {
            'class': rStyle[3], 'count': rCount[3]})
        outFile.write(" <tr><td %(class)s> Ref BuildSet </td>   <td> Source(only)</td><td> +%(count)d </td></tr>\n" % {
            'class': rStyle[2], 'count': rCount[2]})
        outFile.write(" <tr><td %(class)s> New BuildSet </td>   <td> Binary </td>     <td> +%(count)d </td></tr>\n" % {
            'class': rStyle[1], 'count': rCount[1]})
        outFile.write(" <tr><td %(class)s> New BuildSet </td>   <td> Source(only)</td><td> +%(count)d </td></tr>\n" % {
            'class': rStyle[0], 'count': rCount[0]})
        outFile.write(" <tr><td %(class)s> Remved BuildSet </td><td> N/A </td>        <td> %(count)d </td></tr>\n" % {
            'class': rStyle[5], 'count': rCount[5]})
        outFile.write("</tr> </tbody></table>\n")

        style = 'ok'
        if rCount[0] > 0:
            style = 'error'
        elif rCount[1] > 0:
            style = 'warning'
        outFile1 = open(self.appDir + '/status', 'w')
        outFile1.write(style)
        outFile1.close()

        outFile.write("<h4>Ref/New Application/BuildSet:</h4><ul>")
        outFile.write("<li><a href='RefAppSet'>Ref. Application Set</a></li>\n")
        outFile.write("<li><a href='RefBuildSet'>Ref. Build Set</a></li>\n")
        outFile.write("<li><a href='packages_source'>New BuildSet (sources)</a></li>\n")
        outFile.write("<li><a href='packages_binary'>New BuildSet (binary)</a></li>\n")
        outFile.write("<li><a href='tools_source'>External Tools (sources)</a></li>\n")
        outFile.write("<li><a href='tools_binary'>External Tools (binary)</a></li></ul><br>\n")

        outFile.write("""<table border="1"><thead><tr><th><b>#/status</b></th><th><b>Package</b></th><th><b>BuildSet(src)</b></th><th><b>BuildSet(bin)</b></th>
                         <th><b>Ref BuildSet</b></th><th><b>Ref. AppSet</b></th></tr></thead><tbody>\n""")

        cnt = 0
        for i in range(0, 6):
            items = res[i]
            for pack in items:
                cnt += 1
                data = self.getPackageDetail(pack, pData)
                outFile.write(
                    "<tr><td %(class)s> %(count)d </td><td> %(pack)s </td>" % {'class': rStyle[i], 'count': cnt,
                                                                               'pack': pack})
                for x in self.getPackageDetail(pack, pData):
                    outFile.write("<td> %(count)d </td>" % {'count': x})
                outFile.write("</tr>\n")
        outFile.write("</tbody></table>\n")

        inFile = open(scriptPath + '/IBPageTail.txt')
        for l in inFile.readlines(): outFile.write(l)
        inFile.close()
        outFile.close()

        return


# ================================================================================

def usage():
    print("usage:", os.path.basename(
        sys.argv[0]), " --ignominy <ignominyDir> --release <releaseDir> --cmsdist <dir> --application <fwlite|online>")
    return


# ================================================================================

def main():
    import getopt
    options = sys.argv[1:]
    try:
        opts, args = getopt.getopt(options, 'h',
                                   ['help', 'ignominy=', 'release=', 'cmsdist=', 'application='])
    except getopt.GetoptError as msg:
        print(msg)
        usage()
        sys.exit(-2)

    ignominyDir = None
    rel = None
    cmsdist = None
    app = 'fwlite'

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()

        if o in ('--ignominy',):
            ignominyDir = a

        if o in ('--release',):
            rel = a

        if o in ('--cmsdist',):
            cmsdist = a

        if o in ('--application',):
            app = a

    if not (rel and cmsdist and ignominyDir):
        print("ERROR: Missing command-line arguments.")
        usage()
        sys.exit(-2)

    ab = AppBuildSet(rel, cmsdist, app)
    try:
        ab.run(ignominyDir)
        ab.generateHTML()
    except Exception as e:
        print("ERROR: Caught exception: " + str(e))

    return


# ================================================================================

if __name__ == "__main__":
    main()
