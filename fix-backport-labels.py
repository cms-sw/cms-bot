#!/usr/bin/env python
import re
from github import Github
from os.path import expanduser
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from categories import CMSSW_L2, CMSSW_L1
from releases import RELEASE_MANAGERS, SPECIAL_RELEASE_MANAGERS
setdefaulttimeout(120)

releaseManagers=list(set(CMSSW_L1 + CMSSW_L2.keys() + SPECIAL_RELEASE_MANAGERS + [ m for rel in RELEASE_MANAGERS for m in rel ]))

parser = OptionParser(usage="%prog <pull-request-id>")
parser.add_option("-n", "--dry-run",    dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default="cms-sw/cmssw")
opts, args = parser.parse_args()

if len(args) != 0: parser.error("Too many/few arguments")
  
gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
repo = gh.get_repo(opts.repository)
label = [ repo.get_label("backport") ]
issues = repo.get_issues(state="open", sort="updated", labels=label)
  
for issue in issues:
  if not issue.pull_request: continue
  api_rate_limits(gh)
  backport_pr=None
  body_firstline = issue.body.encode("ascii", "ignore").split("\n",1)[0].strip()
  if re.match("^backport\s+(of\s+|)#(\d+)$", body_firstline, re.I):
    print body_firstline.split("#",1)
    backport_pr=body_firstline.split("#",1)[-1]
  for comment in issue.get_comments():
    if not comment.user.login in releaseManagers + [issue.user.login]: continue
    comment_msg = comment.body.encode("ascii", "ignore").split("\n",1)[0].strip()
    if re.match("^backport\s+(of\s+|)#(\d+)$", comment_msg, re.I):
      print comment_msg.split("#",1)
      backport_pr=comment_msg.split("#",1)[-1]
  if backport_pr and re.match("^[1-9][0-9]+$",backport_pr):
    print issue.number, backport_pr
    try:
      pr   = repo.get_pull(int(backport_pr))
      if repo.get_pull(int(backport_pr)).merged:
        labels = list(set([x.name for x in issue.labels if x.name!="backport"]+["backport-ok"]))
        issue.edit(labels=labels)
        print issue.number,"New Labels:",labels
    except Exception, e:
      print e
