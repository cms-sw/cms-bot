#!/usr/bin/env python
from github import Github, GithubException
from sys import exit
from os.path import expanduser
from argparse import ArgumentParser
from datetime import datetime
import re
import urllib2
from time import sleep
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, RELEASE_BRANCH_CLOSED, CMSSW_DEVEL_BRANCH
from socket import setdefaulttimeout
setdefaulttimeout(120)
import json

if __name__ == "__main__":
  parser = ArgumentParser()
  parser.add_argument("-s", "--source", dest="source", help="Source repository, default is master", type=str, default="master")
  parser.add_argument("-d", "--dest")
  parser.add_argument("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default=gh_user+"/"+gh_cmssw)
  parser.add_argument("-n", "-dry-run", dest="dryRun", default=False, action="store_true")
  args = parser.parse_args()

  if args.source == args.dest:
    print "Source and destination branches are same"
    exit(1)
  elif (not args.source) or (not args.dest):
    print "Missing source or destination branch"
    exit(1)

  GH_TOKEN = open(expanduser("~/.github-token")).read().strip()
  gh = Github(login_or_token=GH_TOKEN)

  repo = gh.get_repo(args.repository)
  srcMilestone = repo.get_milestone(RELEASE_BRANCH_MILESTONE[args.source])
  desMilestone = repo.get_milestone(RELEASE_BRANCH_MILESTONE[args.dest])
  print srcMilestone, desMilestone
  if srcMilestone.number==desMilestone.number:
    print "Error: Same milestone %s for %s and %s branches" % (srcMilestone,args.source,args.dest)
    exit(1)

  pulls = repo.get_pulls(base=args.source, state="open")
  for pr in pulls:
    print "Wroking on PR ",pr.number,"with milestone",pr.milestone.number
    if pr.milestone.number == srcMilestone.number:
      if not args.dryRun:
        issue = repo.get_issue(pr.number)
        issue.edit(milestone=desMilestone)
      print "  Updated milestone:",desMilestone.number
    elif pr.milestone.number == desMilestone.number:
      continue
    else:
      print "  Invalid Source Milestone:",pr.milestone.number

