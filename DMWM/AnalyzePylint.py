#! /usr/bin/env python

from __future__ import print_function

import json
import os

from github import Github

summaryMessage = ''
longMessage = ''
reportOn = {}
failed = False

with open('pylintReport.json', 'r') as reportFile:
    report = json.load(reportFile)

    for filename in report.keys():
        fileReport = report[filename]
        if 'test' in fileReport and 'base' not in fileReport:
            testReport = fileReport['test']
            if not 'score' in testReport:
                continue
            reportOn[filename] = True
            summaryMessage += '* New file %s with score %s, %s warnings, and %s errors\n' % (filename, testReport['score'], testReport['warnings'], testReport['errors'])
        if 'test' in fileReport and 'base'  in fileReport:
            testReport = fileReport['test']
            baseReport = fileReport['base']
            if not 'score' in testReport or not 'score' in baseReport:
                continue
            if float(testReport['score']) < float(baseReport['score']):
                reportOn[filename] = True
                summaryMessage += '* Score for %s decreased from %s to %s\n' % (filename, baseReport['score'], testReport['score'])
            if testReport['errors'] > baseReport['errors']:
                reportOn[filename] = True
                summaryMessage += '* Errors for %s increased from %s to %s\n' % (filename, baseReport['errors'], testReport['errors'])
            if testReport['warnings'] > baseReport['warnings']:
                reportOn[filename] = True
                summaryMessage += '* Warnings for %s increased from %s to %s\n' % (filename, baseReport['warnings'], testReport['warnings'])

    for filename in report.keys():
        comments = 0
        fileReport = report[filename]
        if 'test' in fileReport:
            testReport = fileReport['test']
            if not 'score' in testReport:
                continue
            if float(testReport['score']) < 8.0 or filename in reportOn:
                if float(testReport['score']) < 8.0:
                    failed = True
                    longMessage += '\n%s fails the pylint check. Report follows:\n' % filename
                elif filename in reportOn:
                    longMessage += '\n%s got worse in pylint. Report follows:\n' % filename
                else:
                    longMessage += '\nPylint report for %s follows:\n' % filename
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

issueID = None

if 'ghprbPullId' in os.environ:
    issueID = os.environ['ghprbPullId']

message = 'No pylint warnings for pull request %s:\n' % issueID


if summaryMessage or longMessage:
    message = 'Summary of pylint changes for pull request %s:\n' % issueID + summaryMessage
    message += longMessage

gh = Github(os.environ['DMWMBOT_TOKEN'])

repoName = '%s/%s' % (os.environ['WMCORE_REPO'], 'WMCore') # Could be parameterized

issue = gh.get_repo(repoName).get_issue(int(issueID))
if len(message) > 250000:
    message = message[:250000]
issue.create_comment('%s' % message)

if failed:
    print('Testing of python code. DMWM-FAIL-PYLINT')
else:
    print('Testing of python code. DMWM-SUCCEED-PYLINT')
