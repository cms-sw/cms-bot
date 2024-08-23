#!/usr/bin/env python3
from datetime import datetime

from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import api_rate_limits

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
from github_utils import get_last_commit

gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
api_rate_limits(gh)
repo = gh.get_repo(opts.repository)
label = [repo.get_label("future-commit")]
cnt = 0
for issue in repo.get_issues(state="open", sort="updated", labels=label):
    pr = issue.pull_request
    if not pr:
        continue
    last_commit = get_last_commit(pr)
    if last_commit is None:
        continue
    if last_commit.commit.committer.date > datetime.utcnow():
        continue
    cnt += 1
    with open("cms-bot-%s-%s.txt" % (repo.name, cnt), "w") as prop:
        prop.write("FORCE_PULL_REQUEST=%s\n" % issue.number)
        prop.write("REPOSITORY=%s\n" % opts.repository)
api_rate_limits(gh)
