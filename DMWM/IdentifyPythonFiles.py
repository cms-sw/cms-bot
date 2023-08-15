#! /usr/bin/env python3

from __future__ import print_function, division

import os
from optparse import OptionParser

usage = "usage: %prog [options] list_of_files.txt"
parser = OptionParser(usage)
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("You must supply a file with a list of files to check")

list_of_files = args[0]

with open(list_of_files, 'r') as changedFiles:
    for fileName in changedFiles:
        fileName = fileName.strip()
        if not fileName:
            continue
        if fileName.endswith('.py'):
            print(fileName)
            continue
        try:
            with open(fileName, 'r') as pyFile:
                pyLines = pyFile.readlines()
                if 'python' in pyLines[0]:
                    print(fileName)
                    continue
        except IOError:
            pass
