#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser, exists
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from json import dumps, load
import re
setdefaulttimeout(120)

def process(repo, prId, prCache):
  data = {}
  issue = repo.get_issue(prId)
  if not issue.pull_request:
    print("WARNING: Only cache Pull requests, %s is an issue." % prId)
    return data
  pr = repo.get_pull(prId)
  if prCache and exists(prCache):
    refData = load(open(prCache))
    if 'freeze' in refData:
      data['freeze'] = refData['freeze']
      data['auther_sha'] = refData['auther_sha']
      data['merge_commit_sha'] = refData['merge_commit_sha']
  data['number']   = issue.number
  data['user']     = issue.user.login.encode("ascii", "ignore")
  data['title']    = issue.title.encode("ascii", "ignore")
  data['comments'] = issue.comments
  data['labels']   = [x.name.encode("ascii", "ignore") for x in issue.labels]
  if issue.body: data['body']=issue.body.encode("ascii", "ignore")
  else: data['body']=""
  if issue.milestone: data['milestone']=issue.milestone.title.encode("ascii", "ignore")

  data['branch']          = pr.base.ref.encode("ascii", "ignore")
  data['created_at']      = pr.created_at.strftime("%s")
  data['updated_at']      = pr.updated_at.strftime("%s")
  if pr.head.user: data['author'] = pr.head.user.login.encode("ascii", "ignore")
  data['auther_ref']      = pr.head.ref.encode("ascii", "ignore")
  if not 'freeze' in data: data['auther_sha'] = pr.head.sha.encode("ascii", "ignore")
  data['review_comments'] = pr.review_comments
  data['commits']         = pr.commits
  data['additions']       = pr.additions
  data['deletions']       = pr.deletions
  data['changed_files']   = pr.changed_files
  data['state']           = pr.state
  if pr.state == "closed":
    data['closed_at'] = pr.closed_at.strftime("%s")
    if pr.merged:
      data['merged_at'] = pr.merged_at.strftime("%s")
      data['merged_by'] = pr.merged_by.login.encode("ascii", "ignore")
      if not 'freeze' in data:
        if pr.merge_commit_sha:data['merge_commit_sha'] = pr.merge_commit_sha.encode("ascii", "ignore")
        else: data['merge_commit_sha']=""
  data['release-notes'] = []
  REGEX_RN = re.compile('^release(-| )note(s|)\s*:\s*',re.I)
  if issue.body:
    msg = issue.body.encode("ascii", "ignore").strip()
    if REGEX_RN.match(msg): data['release-notes'].append(REGEX_RN.sub('',msg).strip())
  for comment in issue.get_comments():
    if not comment.body: continue
    msg = comment.body.encode("ascii", "ignore").strip()
    if REGEX_RN.match(msg):
      data['release-notes'].append(REGEX_RN.sub('',msg).strip())
  return data

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <pull-request-id> <pr-cache-file>")
  parser.add_option("-n", "--dry-run",    dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default="cms-sw/cmssw")
  parser.add_option("-u", "--user",       dest="user",       help="GH API user.", type=str, default="")
  opts, args = parser.parse_args()

  if len(args) != 2:
    parser.error("Too many/few arguments")
  prId = int(args[0])
  ghtoken=".github-token"
  if opts.user: ghtoken=".github-token-"+opts.user

  gh = Github(login_or_token=open(expanduser("~/"+ghtoken)).read().strip())
  api_rate_limits(gh)
  data = process(gh.get_repo(opts.repository), prId, args[1])
  if opts.dryRun: print(dumps(data))
  else:
    j = open(args[0]+".json","w")
    j.write(dumps(data,sort_keys=True))
    j.close()

