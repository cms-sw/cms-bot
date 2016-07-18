#!/usr/bin/env python
from github import Github
from os.path import expanduser
from optparse import OptionParser
import sys
from process_pr import modify_comment, find_last_comment
from process_pr import TRIGERING_TESTS_MSG
from socket import setdefaulttimeout
setdefaulttimeout(120)

valid_types = {}
valid_types['JENKINS_TEST_URL']=[ "^\s*"+TRIGERING_TESTS_MSG+".*$", None ]
all_types = "|".join(valid_types)
if __name__ == "__main__":
  parser = OptionParser(usage="%prog [-n|--dry-run] [-r|--repository <repo>] -t|--type "+all_types+" -m|--message <message> <pull-request-id>")
  parser.add_option("-n", "--dry-run",    dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default="cms-sw/cmssw")
  parser.add_option("-t", "--type",       dest="msgtype",    help="Message type e.g. JENKINS_TEST_URL", type=str, default=None)
  parser.add_option("-m", "--message",    dest="message",    help="Message to be appened to the existing comment e.g. url of jenkins test job.", type=str, default=None)

  opts, args = parser.parse_args()
  if len(args) != 1: parser.error("Too many/few arguments")
  if not opts.message: parser.error("Missing message to append")
  if not opts.msgtype:  parser.error("Missing message type")
  if not opts.msgtype in valid_types:  parser.error("Invalid message type "+opts.msgtype)
  
  gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
  issue = gh.get_repo(opts.repository).get_issue(int(args[0]))
  last_comment = find_last_comment(issue, "cmsbuild" ,valid_types[opts.msgtype][0])
  if not last_comment:
    print "Warning: Not comment matched"
    sys.exit(1)
  print last_comment.body.encode("ascii", "ignore")
  sys.exit(modify_comment(last_comment,valid_types[opts.msgtype][1],opts.message,opts.dryRun))
