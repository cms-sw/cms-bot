#!/usr/bin/env python3
from __future__ import print_function
import sys
from sys import exit,argv
from re import match
from os.path import expanduser, dirname, abspath, join, exists
from argparse import ArgumentParser
from socket import setdefaulttimeout

from github_utils import get_pr, get_issue_comments, merge_pr, edit_issue, \
  create_issue_comment

setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(argv[0]))

def process_pr(repo: str, issue: dict, dryRun: bool):
  from cmsdist_merge_permissions import USERS_TO_TRIGGER_HOOKS, getCommentCommand, hasRights
  print("Issue state:", issue["state"])
  prId    = issue["number"]
  pr      = None
  branch  = None
  cmdType = None
  chg_files= []
  if issue["pull_request"]:
    pr   = get_pr(repo, prId)
    branch = pr["base"]["ref"]
    print("PR merged:", pr["merged"])
    if pr["merged"]: return True
    from process_pr import get_changed_files
    chg_files = get_changed_files(repo, pr)
  USERS_TO_TRIGGER_HOOKS.add("cmsbuild")
  for comment in get_issue_comments(repo, issue):
    commenter = comment["user"]["login"]
    if not commenter in USERS_TO_TRIGGER_HOOKS: continue
    comment_msg = comment["body"].encode("ascii", "ignore")
    comment_lines = [ l.strip() for l in comment_msg.split("\n") if l.strip() ][0:1]
    print("Comment first line: %s => %s" % (commenter, comment_lines))
    if not comment_lines: continue
    first_line = comment_lines[0]
    if commenter == "cmsbuild":
      if not cmdType: continue
      if match("^Command\s+"+cmdType+"\s+acknowledged.$",first_line):
        print("Acknowledged ",cmdType)
        cmdType = None
      continue
    cmd = getCommentCommand(first_line)
    if not cmd: continue
    if (cmd == "ping") and cmdType: continue
    if cmd == "merge" and not pr: continue
    if not hasRights (commenter, branch, cmd, chg_files): continue
    cmdType = cmd
    print("Found: Command %s issued by %s" % (cmdType, commenter))
  if not cmdType: return True
  print("Processing ",cmdType)
  if dryRun: return True
  if issue["state"] == "open":
    if cmdType == "merge": merge_pr(repo, prId)
    if cmdType == "close": edit_issue(repo, prId, {'state': "closed"})
  elif cmdType == "open": edit_issue(repo, prId, {'state': "open"})
  create_issue_comment(repo, prId, "Command "+cmdType+" acknowledged.")
  return True

if __name__ == "__main__":
  parser = ArgumentParser()
  parser.add_argument("-n", "--dry-run", dest="dryRun", action="store_true", help="Do not modify Github", default=False)
  parser.add_argument("prId", help="Pull request id", nargs=1)
  #parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmsdist.", type=str, default="cms-sw/cmsdist")
  args = parser.parse_args()

  prId = int(args.prId[0])
  
  repo_dir = join(SCRIPT_DIR,'repos',"cms-sw/cmsdist".replace("-","_"))
  if exists(join(repo_dir,"repo_config.py")): sys.path.insert(0,repo_dir)
  import repo_config

  repo = "cms-sw/cmsdist"
  if not process_pr(repo, prId, args.dryRun): exit(1)
  exit (0)
