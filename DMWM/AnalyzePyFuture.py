#! /usr/bin/env python

from __future__ import print_function, division

with open('addedFiles.txt', 'r') as addedFiles:
    for fileName in addedFiles:
        fileName = fileName.strip()
        if fileName.endswith('__init__.py'):
            continue
        with open(fileName, 'r') as pyFile:
            pyLines = pyFile.readlines()
            if fileName.endswith('.py') or 'python' in  pyLines[0]:
                foundDivision = False
                for line in pyLines:
                    if '__future__' in line and 'division' in line:
                        foundDivision = True
                if not foundDivision:
                    print ("* New file %s does not use python 3 division. Please add `from __future__ import division`.\n" % fileName)
