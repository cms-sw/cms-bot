#! /usr/bin/env python

from __future__ import print_function

import os

from github import Github

summaryMessage = ""
reportOn = {}
failed = False

with open("added.message", "r") as messageFile:
    lines = messageFile.readlines()

    if len(lines):
        summaryMessage += (
            "Imports for Python3 compatability missing in new files. Please fix this:\n"
        )

        summaryMessage += "".join(lines)
        summaryMessage += "\n\n"
        failed = True

with open("test.patch", "r") as patchFile:
    lines = patchFile.readlines()

    if len(lines):
        summaryMessage += "Pre-python 2.6 constructs are introduced by this pull request. This must be fixed. Suggested patch follows:\n\n"

        summaryMessage += "```diff\n"
        summaryMessage += "".join(lines)
        summaryMessage += "\n```\n\n"
        failed = True

with open("idioms.patch", "r") as patchFile:
    lines = patchFile.readlines()

    if len(lines):
        summaryMessage += "Pre-python 2.6 idioms found in changed files. Please consider updating the code. Suggested patch follows:\n\n"

        summaryMessage += "```diff\n"
        summaryMessage += "".join(lines)
        summaryMessage += "\n```\n\n"


issueID = None

if "ghprbPullId" in os.environ:
    issueID = os.environ["ghprbPullId"]

gh = Github(os.environ["DMWMBOT_TOKEN"])
codeRepo = os.environ.get("CODE_REPO", "WMCore")
repoName = "%s/%s" % (os.environ["WMCORE_REPO"], codeRepo)

issue = gh.get_repo(repoName).get_issue(int(issueID))
if len(summaryMessage) > 250000:
    summaryMessage = summaryMessage[:250000]
if summaryMessage:
    issue.create_comment("%s" % summaryMessage)

if failed:
    print("Testing of python code. DMWM-FAIL-PY27")
else:
    print("Testing of python code. DMWM-SUCCEED-PY27")
