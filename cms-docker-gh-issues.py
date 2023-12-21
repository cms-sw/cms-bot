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
parser.add_argument(
    "-c",
    "--comment-only",
    dest="comment",
    help="Only comment on an existing issue.",
    default=False,
)

args = parser.parse_args()
mgs = ""
if not args.repo:
    parser.error("Missing Repo")
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

if args.comment == False:
    issues_curl = (
        "curl -s 'https://api.github.com/search/issues?q=+repo:%s+in:title+type:issue%s'"
        % (args.repo, label_str)
    )
    pulls_curl = (
        "curl -s 'https://api.github.com/repos/%s/pulls?q=+is:open+label:%s'"
        % (args.repo, args.labels[0])
    )

    print("Checking existing Issue", issues_curl)
    exit_code, issues_obj = run_cmd(issues_curl)
    issues_dict = json.loads(issues_obj)
    print("Existing Issues: " + str(issues_dict["total_count"]))

    # We should have only one matching issue
    assert issues_dict["total_count"] <= 1

    if issues_dict["total_count"] == 0:
        print("Creating issue request")
        gh_repo.create_issue(title=args.title, body=msg, labels=args.labels)

        print("Checking existing PR with matching labels", pulls_curl)
        exit_code, pulls_obj = run_cmd(pulls_curl)
        pulls_obj = json.loads(pulls_obj)
        urls = ""
        for pull in pulls_obj:
            print(pull["html_url"])
            urls += str(pull["html_url"]) + " "
        print("The following PRs have matching labels: ", urls)

        # Get current issue number
        print("Check newly created Issue", issues_curl)
        exit_code, issues_obj = run_cmd(issues_curl)
        issues_dict = json.loads(issues_obj)
        issue_number = issues_dict["items"][0]["number"]

        # Comment related PRs
        issue_comment = (
            "The following PRs should be probably merged before building the new image: "
            + urls
        )
        print(issue_comment)
        create_issue_comment(gh_repo.full_name, issue_number, issue_comment)
    else:
        # Check state of the issue: open/closed...
        issue_title = issues_dict["items"][0]["title"]
        print(issue_title)
        issue_number = issues_dict["items"][0]["number"]
        print(issue_number)

        state = issues_dict["items"][0]["state"]
        print(state)
        if state == "open":
            print("Issue is already open... Nothing to do!")
        elif state == "closed":
            print("Ready for building!")
            # Process "building" label
            existing_labels = get_issue_labels(gh_repo.full_name, issue_number)
            print(existing_labels)
            for label_obj in existing_labels:
                if label_obj["name"] == "building":
                    print("Build already triggered... Nothing to do!")
                    sys.exit(0)

            add_issue_labels(gh_repo.full_name, issue_number, ["building"])
            # Don't delete property files
            sys.exit(1)

    # Delete property files
    sys.exit(0)
else:
    issues_curl = (
        "curl -s 'https://api.github.com/search/issues?q=+repo:%s+in:title+type:issue%s'"
        % (args.repo, label_str)
    )

    print("Checking existing Issue", issues_curl)
    exit_code, issues_obj = run_cmd(issues_curl)
    print(issues_obj)

    issues_dict = json.loads(issues_obj)
    print("Existing Issues: " + str(issues_dict["total_count"]))

    # We should have only one matching issue
    assert issues_dict["total_count"] <= 1

    if issues_dict["total_count"] == 0:
        print("No matching issues found, skipping...")
    else:
        print("Adding issue comment...")
        issue_title = issues_dict["items"][0]["title"]
        print(issue_title)
        issue_number = issues_dict["items"][0]["number"]
        print(issue_number)
        print("MESSAGE: ", msg)
        create_issue_comment(gh_repo.full_name, issue_number, msg)
