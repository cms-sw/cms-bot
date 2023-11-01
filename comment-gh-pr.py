#!/usr/bin/env python
"""
Makes a comment on Pull request on Github
"""
from __future__ import print_function
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from sys import exit
import re, sys
from socket import setdefaulttimeout
setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(sys.argv[0]))



if __name__ == "__main__":
    parser = OptionParser(usage="%prog -p|--pullrequest <number> -m|--message <message> [-r|--repository <repo>] [-n|--dry-run]")
    parser.add_option("-n", "--dry-run",     dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
    parser.add_option("-r", "--repository",  dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.",  type=str, default="cms-sw/cmssw")
    parser.add_option("-p", "--pullrequest", dest="pr",         help="Github Pull Request Number e.g. 10500",     type="int", metavar="N")
    parser.add_option("-m", "--message",     dest="msg",        help="Message to be added for Github Pull Request", type="str")
    parser.add_option("-R", "--report-file", dest="report_file",help="Message from the file to be added for Github Pull Request", type="str")
    opts, args = parser.parse_args()


    if not opts.pr: parser.error("Missing pull request number : -p|--pullrequest <number>")
    msg = ""
    if opts.msg: msg = re.sub("@N@","\n",opts.msg)
    elif opts.report_file: msg = open(opts.report_file).read()
    else: parser.error("Missing pull request message: -m|--message <message> OR -R|--report-file <file-path>")
    if opts.dryRun:
      print("Addeding Comments:",msg)
    else:
      repo_dir = join(SCRIPT_DIR,'repos',opts.repository.replace("-","_"))
      if exists(join(repo_dir,"repo_config.py")): sys.path.insert(0,repo_dir)
      import repo_config
      gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
      from github_utils import comment_gh_pr
      try:
          comment_gh_pr(gh, opts.repository, opts.pr, msg)
          print("Added comment for %s#%s" % (opts.repository, opts.pr))
          print("Comment message:\n",msg)
      except Exception as e:
          print("Failed to add comment: ",e)
          exit(1)
