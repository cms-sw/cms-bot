#!/usr/bin/env python

# TODO had syntax errors, is this file used ?
from __future__ import print_function

import glob
import os


def pythonNameFromCfgName(cfgName):
    newName = cfgName.replace("-", "_")
    return newName.replace("/data/", "/python/").replace(".cf", "_cf") + ".py"


releaseBase = os.path.expandvars("$CMSSW_RELEASE_BASE/src") + "/"
files = glob.glob(releaseBase + "*/*/data/*cf[fi]")

# give 'em two hours
gracePeriod = 2 * 60 * 60

pkgInfo = {}
pkgList = []
missingFiles = []
for f in files:
    pythonFile = pythonNameFromCfgName(f)
    if os.path.exists(pythonFile):
        if os.path.getmtime(f) > os.path.getmtime(pythonNameFromCfgName(f)) + gracePeriod:
            subsys, pkg, pydir, fname = pythonFile.split("/")
            pkgName = subsys + "_" + pkg
            if pkgName in pkgInfo:
                pkgInfo[pkgName].append(pythonFile)
            else:
                pkgInfo[pkgName] = [pythonFile]
                if pkgName not in pkgList:
                    pkgList.append(pkgName)
            # print f
    else:
        missingFiles.append(pythonFile)
        subsys, pkg, pydir, fname = pythonFile.split("/")
        pkgName = subsys + "_" + pkg
        if pkgName in pkgInfo:
            pkgInfo[pkgName].append(pythonFile)
        else:
            pkgInfo[pkgName] = [pythonFile]
            if pkgName not in pkgList:
                pkgList.append(pkgName)
        # print f

nFiles = 0
pkgList.sort()
for pkg in pkgList:
    print("-" * 80)
    print("Package:", pkg)
    for fName in pkgInfo[pkg]:
        status = "update needed :"
        if fName in missingFiles:
            status = "missing file :"
        print("  ", status, fName)
        nFiles += 1

print("\nFound a total of ", len(pkgList), "problematic packages and ", nFiles, "files.")
