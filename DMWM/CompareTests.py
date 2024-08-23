#!/usr/bin/env python

from __future__ import print_function

import glob
import os
import sys

try:
    from github import Github
except ImportError:
    # DMWM-WMCore-UnitTests and DMWM-WMCorePy3-UnitTests don't really push anything!
    Github = None

import xunitparser

testResults = {}

unstableTests = []

try:
    with open("code/test/etc/UnstableTests.txt") as unstableFile:
        for line in unstableFile:
            unstableTests.append(line.strip())
except:
    print("Was not able to open list of unstable tests")

# Parse all the various nose xunit test reports looking for changes
filePattern = "*/nosetests-*.xml"
if len(sys.argv) == 2:
    filePattern = "*/%s-*.xml" % sys.argv[1]
for kind, directory in [("base", "./MasterUnitTests/"), ("test", "./LatestUnitTests/")]:
    for xunitFile in glob.iglob(directory + filePattern):
        ts, tr = xunitparser.parse(open(xunitFile))
        for tc in ts:
            testName = "%s:%s" % (tc.classname, tc.methodname)
            if testName in testResults:
                testResults[testName].update({kind: tc.result})
            else:
                testResults[testName] = {kind: tc.result}

# Generate a Github report of any changes found

issueID, mode = None, None

if "ghprbPullId" in os.environ:
    issueID = os.environ["ghprbPullId"]
    mode = "PR"
elif "TargetIssueID" in os.environ:
    issueID = os.environ["TargetIssueID"]
    mode = "Daily"

print("Comparing tests for issueID: {} in mode: {}".format(issueID, mode))

message = "Unit test changes for pull request %s:\n" % issueID
if mode == "Daily":
    message = "Unit test changes for most recent test of master branch:\n"

changed = False
stableChanged = False
failed = False
errorConditions = ["error", "failure"]

for testName, testResult in sorted(testResults.items()):
    if "base" in testResult and "test" in testResult and testName in unstableTests:
        if testResult["base"] != testResult["test"]:
            changed = True
            message += "* %s (unstable) changed from %s to %s\n" % (
                testName,
                testResult["base"],
                testResult["test"],
            )
    elif "base" in testResult and "test" in testResult:
        if testResult["base"] != testResult["test"]:
            changed = True
            stableChanged = True
            message += "* %s changed from %s to %s\n" % (
                testName,
                testResult["base"],
                testResult["test"],
            )
            if testResult["test"] in errorConditions:
                failed = True
    elif "test" in testResult:
        changed = True
        stableChanged = True
        message += "* %s was added. Status is %s\n" % (testName, testResult["test"])
        if testResult["test"] in errorConditions:
            failed = True
    elif "base" in testResult:
        changed = True
        stableChanged = True
        message += "* %s was deleted. Prior status was %s\n" % (testName, testResult["base"])
if failed:
    message += "\n\nPreviously working unit tests have failed!\n"

if mode == "Daily":
    # Alan on 25/may/2021: then there is nothing else to be done
    print(message)
    sys.exit(0)

gh = Github(os.environ["DMWMBOT_TOKEN"])
codeRepo = os.environ.get("CODE_REPO", "WMCore")
repoName = "%s/%s" % (os.environ["WMCORE_REPO"], codeRepo)

issue = gh.get_repo(repoName).get_issue(int(issueID))

if not changed and mode == "Daily":
    message = "No changes to unit tests for latest build\n"
elif not changed:
    message = "No changes to unit tests for pull request %s\n" % issueID

if mode == "Daily" and stableChanged:
    issue.create_comment("%s" % message)
elif mode != "Daily":
    issue.create_comment("%s" % message)

if failed:
    print("Testing of python code. DMWM-FAIL-UNIT")
else:
    print("Testing of python code. DMWM-SUCCEED-UNIT")
