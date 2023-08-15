#!/usr/bin/env python3
from __future__ import print_function
from github import Github, GithubException
from os.path import expanduser
from argparse import ArgumentParser
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from socket import setdefaulttimeout
setdefaulttimeout(120)

def create_branch(repo, src_branch, des_branch, dryRun=False):
  print("Creating new branch '%s' based on '%s'" % (des_branch, src_branch))
  base_ref = repo.get_branch(src_branch)
  print("  Base branch %s has sha %s" % (src_branch, base_ref.commit.sha))
  try:
    repo.get_branch(des_branch)
    print("  Branch already exists: ",des_branch)
    return
  except GithubException as e:
    if not "Branch not found" in e.data['message']: raise e
  if not dryRun:
    repo.create_git_ref ("refs/heads/"+des_branch, base_ref.commit.sha)
    print("  Created new branch ",des_branch," based on ",base_ref.commit.sha)
  else:
    print("  DryRun: Creating new branch ",des_branch," based on ",base_ref.commit.sha)
  return

if __name__ == "__main__":
  parser = ArgumentParser()
  parser.add_argument("-c", "--cmssw",   dest="cmssw",  action='append',  type=lambda kv: kv.split("="), help="cmssw branch to be created. formate is key=value")
  parser.add_argument("-d", "--cmsdist", dest="cmsdist", action='append', type=lambda kv: kv.split("="), help="cmsdist branch to be created. formate is key=value")
  parser.add_argument("-n", "-dry-run", dest="dryRun", default=False, action="store_true")
  args = parser.parse_args()

  print(args.cmssw)
  print(args.cmsdist)

  GH_TOKEN = open(expanduser("~/.github-token")).read().strip()
  gh = Github(login_or_token=GH_TOKEN)
  if args.cmssw:
    print("Creating CMSSW Branch(es)")
    repo = gh.get_repo(gh_user+"/"+gh_cmssw)
    for br_pair in args.cmssw:
      create_branch(repo, br_pair[0], br_pair[1], args.dryRun)
  if args.cmsdist:
    print("\nCreating CMSDIST Branch(es)")
    repo = gh.get_repo(gh_user+"/"+gh_cmsdist)
    for br_pair in args.cmsdist:
      create_branch(repo, br_pair[0], br_pair[1], args.dryRun)
    
  

