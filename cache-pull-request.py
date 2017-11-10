#!/usr/bin/env python
from github import Github
from os.path import expanduser
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from sys import exit
from json import dumps
setdefaulttimeout(120)

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <pull-request-id>")
  parser.add_option("-c", "--commit",     dest="commit",     action="store_true", help="Get last commit of the PR", default=False)
  parser.add_option("-n", "--dry-run",    dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default="cms-sw/cmssw")
  opts, args = parser.parse_args()

  if len(args) != 1:
    parser.error("Too many/few arguments")
  prId = int(args[0])
  
  gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
  if not opts.commit: api_rate_limits(gh)
  repo = gh.get_repo(opts.repository)
  issue = repo.get_issue(prId)
  if not issue.pull_request:
    print "ERROR: Only cache Pull requests, %s is an issue." % prId
    exit(1)
  pr = repo.get_pull(prId)
  if not pr.merged:
    print "ERROR: PR is not merged yet"
    exit(1)
  data = {}
  data['user']=issue.user.login.encode("ascii", "ignore")
  data['title']=issue.title.encode("ascii", "ignore")
  data['body']=issue.body.encode("ascii", "ignore")
  data['branch']=pr.base.ref.encode("ascii", "ignore")
  data['created_at']=pr.created_at.strftime("%s")
  data['updated_at']=pr.updated_at.strftime("%s")
  data['merged_at']=pr.merged_at.strftime("%s")
  data['merged_by']=pr.merged_by.login.encode("ascii", "ignore")
  data['merge_commit_sha']=pr.merge_commit_sha.encode("ascii", "ignore")
  if issue.milestone: data['milestone']=issue.milestone.title.encode("ascii", "ignore")
  data['merged_by']=pr.merged_by.login.encode("ascii", "ignore")
  data['author']=pr.head.user.login.encode("ascii", "ignore")
  data['auther_ref']=pr.head.ref.encode("ascii", "ignore")
  data['auther_sha']=pr.head.sha.encode("ascii", "ignore")
  data['comments']=issue.comments
  data['review_comments']=pr.review_comments
  data['commits']=pr.commits
  data['additions']=pr.additions
  data['deletions']=pr.deletions
  data['changed_files']=pr.changed_files
  data['labels']=[x.name.encode("ascii", "ignore") for x in issue.labels]
  if opts.dryRun: print dumps(data)
  else:
    j = open(args[0]+".json","w")
    j.write(dumps(data,sort_keys=True))
    j.close()

