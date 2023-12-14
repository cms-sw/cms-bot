#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser, abspath, dirname, join, exists
import sys, re, json
from argparse import ArgumentParser
from _py2with3compatibility import run_cmd
from github_utils import add_issue_labels, get_issue_labels

SCRIPT_DIR = dirname(abspath(sys.argv[0]))

parser = ArgumentParser()
parser.add_argument(
    "-r",
    "--repository",
    dest="repo",
    help="Github Repositoy name e.g cms-sw/cms-bot",
    type=str,
)
parser.add_argument("-t", "--title", dest="title", help="Issue title", type=str)
parser.add_argument(
    "-m",
    "--message",
    dest="msg",
    help="Message to be posted s body of the GH issue",
    type=str,
    default="",
)
parser.add_argument(
    "-l",
    "--labels",
    dest="labels",
    nargs="*",
    help="Labels for the GH issue (undefined number)",
    default="",
)

args = parser.parse_args()
mgs = ""
if not args.repo:
    parser.error("Missing Repo")
if not args.title:
    parser.error("Missing PR title")
if args.msg:
    msg = re.sub("@N@", "\n", args.msg)
else:
    parser.error("Missing issue message: -m|--message <message>")

print("Authenticating to Github and connecting to repo")
repo_dir = join(SCRIPT_DIR, "repos", args.repo.replace("-", "_"))
if exists(join(repo_dir, "repo_config.py")):
    sys.path.insert(0, repo_dir)
import repo_config

gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
gh_repo = gh.get_repo(args.repo)
print("Authentication succeeeded to " + str(gh_repo.full_name))

label_str = "+label:".join([""] + [str(label) for label in args.labels])

cmd = (
    "curl -s 'https://api.github.com/search/issues?q=+repo:%s+in:title+type:issue%s'"
    % (args.repo, label_str)
)

print("Checking existing Issue", cmd)
exit_code, output = run_cmd(cmd)
issues_dict = json.loads(output)

print("Existing Issues: " + str(issues_dict["total_count"]))

# We should have only one matching issue
assert issues_dict["total_count"] <= 1

if issues_dict["total_count"] == 0:
    print("Creating issue request...")
    gh_repo.create_issue(title=args.title, body=msg, labels=args.labels)
else:
    # Check state of the issue: open/closed...
    issue_title = issues_dict["items"][0]["title"]
    print("Issue exists with title: " + issue_title)
    issue_number = issues_dict["items"][0]["number"]

    state = issues_dict["items"][0]["state"]
    if state == "open":
        print("Issue is open... Nothing to do!")
    elif state == "closed":
        print("Issue is closed... Ready for building!")
        # Process "building" label
        existing_labels = get_issue_labels(gh_repo.full_name, issue_number)
        for label_obj in existing_labels:
            if label_obj["name"] == "building":
                print("Build already triggered... Nothing to do!")
                # Don't trigger building job
                sys.exit(0)

        add_issue_labels(gh_repo.full_name, issue_number, ["building"])
        # Trigger building job
        sys.exit(1)

# Don't trigger building job
sys.exit(0)
