#! /usr/bin/env python3

import json

from optparse import OptionParser

usage = "usage: %prog [options] message"
parser = OptionParser(usage)
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("You must supply a label")

label = args[0]

try:
    with open('pylintReport.json', 'r') as reportFile:
        report = json.load(reportFile)
except IOError:
    report = {}

warnings = 0
errors = 0
comments = 0
refactors = 0
score = 0

with open('pylint.out', 'r') as pylintFile:
    for line in pylintFile:
        if line.startswith('Your code has been rated at '):
            scorePart = line.strip('Your code has been rated at ')
            score = scorePart.split('/')[0]
            try:
                if not filename in report:
                    report[filename] = {}
                if not label in report[filename]:
                    report[filename][label] = {}
                if filename and label:
                    report[filename][label]['score'] = score
            except NameError:
                print("Score of %s found, but no filename" % score)

        parts = line.split(':')
        if len(parts) != 3:
            continue
        try:
            newFilename, lineNumber, rawMessage = parts
            newFilename = newFilename.strip()
            if not newFilename:  # Don't update filename if we didn't find one
                continue
            lineNumber = int(lineNumber)
            filename = newFilename
            rmParts = rawMessage.split(']', 1)
            rawCode = rmParts[0].strip()
            message = rmParts[1].strip()
            severity = rawCode[1:2]
            code = rawCode[2:6]
            shortMsg = rawCode[7:]
            msgParts = shortMsg.split(',')
            objectName = msgParts[1].strip()

            if severity == 'R':
                refactors += 1
            elif severity == 'W':
                warnings += 1
            elif severity == 'E':
                errors += 1
            elif severity == 'C':
                comments += 1

            if not filename in report:
                report[filename] = {}

            if not label in report[filename]:
                report[filename][label] = {}
            if not 'events' in report[filename][label]:
                report[filename][label]['events'] = []
            report[filename][label]['events'].append((lineNumber, severity, code, objectName, message))

            report[filename][label]['refactors'] = refactors
            report[filename][label]['warnings'] = warnings
            report[filename][label]['errors'] = errors
            report[filename][label]['comments'] = comments

        except ValueError:
            continue

with open('pylintReport.json', 'w') as reportFile:
    json.dump(report, reportFile, indent=2)
    reportFile.write('\n')






