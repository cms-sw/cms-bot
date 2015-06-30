#! /usr/bin/env python

import json

summaryMessage = ''
longMessage = ''

with open('pylintReport.json', 'r') as reportFile:
    report = json.load(reportFile)

    for filename in report.keys():
        fileReport = report[filename]
        if 'test' in fileReport and 'base' not in fileReport:
            testReport = fileReport['test']
            summaryMessage += '* New file %s with score %s, %s warnings, and %s errors\n' % (filename, testReport['score'], testReport['warnings'], testReport['errors'])
        if 'test' in fileReport and 'base'  in fileReport:
            testReport = fileReport['test']
            baseReport = fileReport['base']
            if testReport['score'] < baseReport['score']:
                summaryMessage += '* Score for %s decreased from %s to %s\n' % (filename, baseReport['score'], testReport['score'])
            if testReport['errors'] > baseReport['errors']:
                summaryMessage += '* Errors for %s increased from %s to %s\n' % (filename, baseReport['errors'], testReport['errors'])
            if testReport['warnings'] > baseReport['warnings']:
                summaryMessage += '* Warnings for %s increased from %s to %s\n' % (filename, baseReport['warnings'], testReport['warnings'])

    for filename in report.keys():
        comments = 0
        fileReport = report[filename]
        if 'test' in fileReport:
            testReport = fileReport['test']
            if testReport['score'] < 8.0:
                longMessage += '%s fails the pylint check. Report follows:\n' % filename
                for event in testReport['events']:
                    if event[1] == 'C': # Severity
                        comments += 1
                        continue
                    if event[1] == 'I': # Severity
                        continue
                    longMessage += '* Line %s ' % (event[0])
                    if  event[3]: # Module
                        longMessage += 'in %s ' % event[3]
                    longMessage += '%s%s %s\n' % (event[1], event[2], event[4])
                longMessage += "* plus %s comments on code style\n" % comments

if summaryMessage:
    summaryMessage = 'Summary of pylint changes for this pull request:\n' + summaryMessage



print summaryMessage
if longMessage:
    print longMessage