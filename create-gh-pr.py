#!/usr/bin/env python
import sys
from github import Github, GithubException
from os.path import expanduser

#Get pull request info from cmdline
pr_repo=sys.argv[1]
pr_title = sys.argv[2]
pr_base_branch= sys.argv[3]
pr_new_branch = sys.argv[4]
#authenticate to Github and connect to repo
gh = Github(login_or_token = open(expanduser("~/.github-token")).read().strip())
gh_repo = gh.get_repo(pr_repo)

#make pull request
gh_repo.create_pull(title = pr_title, body='' , base = pr_base_branch, head = pr_new_branch )

