#!/usr/bin/env python
from github import Github
from os.path import expanduser
from sys import argv , exit

print "\nChecking arguments\n"
if len(argv) < 5 :
  print "Usage:  %s <user/repo_name> <pr_title> <base_branch> <feature_branch> \n" % argv[0]
  exit(1)

#Get pull request info
pr_repo = argv[1]
pr_title = argv[2]
pr_base_branch = argv[3]
pr_new_branch = argv[4]

print "Authenticating to Github and connecting to repo"
gh = Github(login_or_token = open(expanduser("~/.github-token")).read().strip())
print "Authentication succeeeded"
gh_repo = gh.get_repo(pr_repo)

print "Creating pull request"
gh_repo.create_pull(title = pr_title, body = '' , base = pr_base_branch, head = pr_new_branch )

