#!/usr/bin/env python
# TODO is this file used?
from __future__ import print_function

import os
import re

try:
    scriptPath = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptPath = os.path.dirname(os.path.abspath(sys.argv[0]))

if scriptPath not in sys.path:
    sys.path.append(scriptPath)
sys.path.append(os.path.join(scriptPath,"python"))


class LibDepChecker(object):
    def __init__(self, startDir=None, plat='slc6_amd64_gcc493'):
        self.plat = plat
        if not startDir:
            startDir = os.getcwd()
        self.startDir = startDir

    def doCheck(self):
        import glob
        pkgDirList = glob.glob(self.startDir + '/src/[A-Z]*/*')
        errMap = {}
        for pkg in pkgDirList:
            if not os.path.isdir(pkg):
                continue
            pkg = re.sub('^' + self.startDir + '/src/', '', pkg)
            missing = self.checkPkg(pkg)
            if missing:
                errMap[pkg] = missing

        from pickle import Pickler
        summFile = open('libchk.pkl', 'wb')
        pklr = Pickler(summFile, protocol=2)
        pklr.dump(errMap)
        summFile.close()

    def checkPkg(self, pkg):
        libName = 'lib' + pkg.replace('/', '') + '.so'
        libPathName = os.path.join(self.startDir, 'lib', self.plat, libName)
        if not os.path.exists(libPathName):
            return []
        cmd = '(cd ' + self.startDir + '/lib/' + self.plat + ';'
        cmd += 'libchecker.pl ' + libName + ' )'
        print("in ", os.getcwd(), " executing :'" + cmd + "'")
        log = os.popen(cmd).readlines()
        return log


def main():
    try:
        import argparse
    except ImportError:
        import archived_argparse as argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--platform', default=None)
    parser.add_argument('-n', '--dryRun', default=False, action='store_true')
    parser.add_argument('-d', '--startDir', default=None)
    args = parser.parse_args()

    # Keeping it for interface compatibility reasons
    # noinspection PyUnusedLocal
    dryRun = args.dryRun
    plat = args.platform or os.environ['SCRAM_ARCH']
    startDir = args.startDir or '.'

    ldc = LibDepChecker(startDir, plat)
    ldc.doCheck()


if __name__ == "__main__":
    main()
