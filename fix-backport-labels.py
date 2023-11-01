#!/usr/bin/env python3
from __future__ import print_function
import re
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from cms_static import ISSUE_SEEN_MSG, CMSBUILD_GH_USER

setdefaulttimeout(120)
import sys

SCRIPT_DIR = dirname(abspath(sys.argv[0]))

parser = OptionParser(usage="%prog")
parser.add_option(
    "-n",
    "--dry-run",
    dest="dryRun",
    action="store_true",
    help="Do not modify Github",
    default=False,
)
parser.add_option(
    "-r",
    "--repository",
    dest="repository",
    help="Github Repositoy name e.g. cms-sw/cmssw.",
    type=str,
    default="cms-sw/cmssw",
)
opts, args = parser.parse_args()

if len(args) != 0:
    parser.error("Too many/few arguments")

repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
if exists(join(repo_dir, "repo_config.py")):
    sys.path.insert(0, repo_dir)
import repo_config
from process_pr import get_backported_pr

gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
repo = gh.get_repo(opts.repository)
label = [repo.get_label("backport")]
issues = repo.get_issues(state="open", sort="updated", labels=label)

for issue in issues:
    if not issue.pull_request:
        continue
    api_rate_limits(gh)
    backport_pr = None
    issue_body = issue.body.encode("ascii", "ignore").decode() if issue.body else ""
    if (issue.user.login == CMSBUILD_GH_USER) and re.match(
        ISSUE_SEEN_MSG, issue_body.split("\n", 1)[0].strip()
    ):
        backport_pr = get_backported_pr(issue_body)
    else:
        for comment in issue.get_comments():
            commenter = comment.user.login
            comment_msg = comment.body.encode("ascii", "ignore").decode()
            # The first line is an invariant.
            comment_lines = [l.strip() for l in comment_msg.split("\n") if l.strip()]
            first_line = comment_lines[0:1]
            if not first_line:
                continue
            first_line = first_line[0]
            if (commenter == CMSBUILD_GH_USER) and re.match(ISSUE_SEEN_MSG, first_line):
                backport_pr = get_backported_pr(comment_msg)
                break
    if backport_pr and re.match("^[1-9][0-9]+$", backport_pr):
        print(issue.number, backport_pr)
        try:
            pr = repo.get_pull(int(backport_pr))
            print("  Backported PR merged:", pr.merged)
            if pr.merged:
                labels = list(
                    set([x.name for x in issue.labels if x.name != "backport"] + ["backport-ok"])
                )
                if not opts.dryRun:
                    issue.edit(labels=labels)
                print(issue.number, "New Labels:", labels)
        except Exception as e:
            print(e)
