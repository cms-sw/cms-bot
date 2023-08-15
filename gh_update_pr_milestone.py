#!/usr/bin/env python3
from __future__ import print_function
from github import Github, GithubException
from sys import exit
from os.path import expanduser
from argparse import ArgumentParser
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from socket import setdefaulttimeout
setdefaulttimeout(120)

if __name__ == "__main__":
  parser = ArgumentParser()
  parser.add_argument("-s", "--source", dest="source", help="Source repository, default is master", type=str, default="master")
  parser.add_argument("-d", "--dest")
  parser.add_argument("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default=gh_user+"/"+gh_cmssw)
  parser.add_argument("-f", "--force",  dest="force", default=False, action="store_true")
  parser.add_argument("-n", "-dry-run", dest="dryRun", default=False, action="store_true")
  args = parser.parse_args()

  if args.source == args.dest:
    print("Source and destination branches are same")
    exit(1)
  elif (not args.source) or (not args.dest):
    print("Missing source or destination branch")
    exit(1)

  GH_TOKEN = open(expanduser("~/.github-token")).read().strip()
  gh = Github(login_or_token=GH_TOKEN)

  repo = gh.get_repo(args.repository)
  desMilestone = None
  milestones = repo.get_milestones()
  for item in repo.get_milestones():
    if args.dest in item.title:
      desMilestone = item
      break
  if not desMilestone:
    print("ERROR: Unable to find milestone for with title %s" % args.dest)
  print("Found milestone: %s" % desMilestone.number)
  pulls = repo.get_pulls(base=args.source, state="open", sort="created", direction="asc")
  for pr in pulls:
    print("Wroking on PR ",pr.number,"with milestone",pr.milestone.number)
    if (not args.force) and (pr.milestone.number == desMilestone.number): continue
    if not args.dryRun:
      issue = repo.get_issue(pr.number)
      if args.force: issue.edit(milestone=None)
      issue.edit(milestone=desMilestone)
    print("  Updated milestone:",desMilestone.number)

