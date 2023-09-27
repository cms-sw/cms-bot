#! /usr/bin/env python

import os

from github import Github
from optparse import OptionParser

usage = "usage: %prog [options] message"
parser = OptionParser(usage)
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("You must supply a message.")

message = args[0]
issueID = None
url = ''

if 'ghprbPullId' in os.environ:
    issueID = os.environ['ghprbPullId']
if 'BUILD_URL' in os.environ:
    url = os.environ['BUILD_URL']
    url = url.replace('cmsjenkins01.cern.ch:443', 'cmssdt.cern.ch')
    url = url.replace('cmsjenkins02.cern.ch:443', 'cmssdt.cern.ch')
    url = url.replace('cmsjenkins10.cern.ch:443', 'cmssdt.cern.ch')
    message += '\nSee %s for details' % url

gh = Github(os.environ['DMWMBOT_TOKEN'])

codeRepo = os.environ.get('CODE_REPO', 'WMCore')
repoName = '%s/%s' % (os.environ['WMCORE_REPO'], codeRepo)

issue = gh.get_repo(repoName).get_issue(int(issueID))

issue.create_comment(message)


