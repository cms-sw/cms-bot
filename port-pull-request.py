#!/usr/bin/env python
from optparse import OptionParser
from os.path import expanduser
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from github import Github
from github_utils import port_pr
from socket import setdefaulttimeout
setdefaulttimeout(120)

if __name__ == "__main__":
  parser = OptionParser( usage="%prog <issue-id>" )
  parser.add_option( "-n" , "--dry-run" , dest="dryRun" , action="store_true", help="Do not post on Github", default=False )
  parser.add_option( "-p", "--pull_request", dest="pull_request" , action="store" , help="Pull request number to be ported", type=int )
  parser.add_option( "-b", "--branch", dest="branch" , action="store" , help="Git branch where this PR should be ported to e.g. CMSSW_7_6_X")
  parser.add_option( "-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default=gh_user+"/"+gh_cmssw)

  opts, args = parser.parse_args( )

  if len( args ) != 0:
    parser.print_help()
    parser.error( "Too many arguments" )

  if not opts.pull_request or not opts.branch:
    parser.print_help()
    parser.error("Too few arguments")

  gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
  port_pr(gh.get_repo(opts.repository), opts.pull_request , opts.branch, opts.dryRun)
