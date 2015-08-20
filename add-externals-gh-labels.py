#!/usr/bin/env python
from github import Github
from os.path import expanduser
from githublabels import LABEL_TYPES, COMMON_LABELS
from categories import COMMON_CATEGORIES, EXTERNAL_CATEGORIES, EXTERNAL_REPOS

all_labels = COMMON_LABELS
for cat in COMMON_CATEGORIES+EXTERNAL_CATEGORIES:
  for lab in LABEL_TYPES:
    all_labels[cat+"-"+lab]=LABEL_TYPES[lab]

gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())

for repo_name in EXTERNAL_REPOS:
  repos = []
  if not "/" in repo_name:
    user = gh.get_user(repo_name)
    for repo in user.get_repos():
      repos.append(repo)
  else:
    repos.append(gh.get_repo(repo_name))

  for repo in repos:
    print "Checking repository ", repo.full_name
    cur_labels = [ lab.name for lab in repo.get_labels() ]
    for lab in all_labels:
      if not lab in cur_labels:
        print "  Creating new label ",lab,"=>",all_labels[lab]
        repo.create_label(lab, all_labels[lab])

