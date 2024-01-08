#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser, abspath, dirname, join, exists
import sys, re
from argparse import ArgumentParser
from _py2with3compatibility import run_cmd, quote

SCRIPT_DIR = dirname(abspath(sys.argv[0]))

parser = ArgumentParser()
parser.add_argument(
    "-r", "--repository", dest="repo", help="GitHub Repository name e.g cms-sw/cms-bot", type=str
)
parser.add_argument("-t", "--title", dest="title", help="Issue title", type=str)
parser.add_argument(
    "-m",
    "--message",
    dest="msg",
    help="Message to be posted in the body of the GH issue",
    type=str,
    default="",
)
parser.add_argument(
    "-R",
    "--report_file",
    dest="report_file",
    help="File name containing the issue message",
    type=str,
    default="",
)
parser.add_argument(
    "-q",
    "--quiet",
    dest="quiet",
    help="Do not take any action if the issue already exists",
    default=False,
)

args = parser.parse_args()
mgs = ""
if not args.repo:
    parser.error("Missing Repo")
if not args.title:
    parser.error("Missing PR title")
if args.msg:
    msg = re.sub("@N@", "\n", args.msg)
elif args.report_file:
    msg = open(args.report_file).read()
else:
    parser.error("Missing issue message: -m|--message <message> OR -R|--report-file <file-path>")

print("Authenticating to Github and connecting to repo")
repo_dir = join(SCRIPT_DIR, "repos", args.repo.replace("-", "_"))
if exists(join(repo_dir, "repo_config.py")):
    sys.path.insert(0, repo_dir)
import repo_config

gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
gh_repo = gh.get_repo(args.repo)
print("Authentication succeeeded to " + str(gh_repo))
cmd = (
    "curl -s 'https://api.github.com/search/issues?q=%s+repo:%s+in:title+type:issue' | grep '\"number\"' | head -1 | sed -e 's|.*: ||;s|,.*||'"
    % (quote(args.title), args.repo)
)
print("Checking existing Issue", cmd)
e, o = run_cmd(cmd)
print("Existing Issues:", e, o)
issue = None
if not e:
    try:
        issue = gh_repo.get_issue(int(o))
    except:
        pass
if issue:
    print(args.quiet)
    if args.quiet == False:
        print("Updating comment")
        issue.create_comment(msg)
else:
    print("Creating issue request")
    gh_repo.create_issue(args.title, msg)
