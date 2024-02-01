#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser, abspath, dirname, join, exists
import sys, re, json, glob
from argparse import ArgumentParser
from _py2with3compatibility import run_cmd
from github_utils import add_issue_labels, create_issue_comment, get_issue_labels

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

if args.comment == False:

    for issue in gh_repo.get_issues(state="open", labels=[str(label) for label in args.labels]):
        print("Issue already opened... Nothing to do!")
        # Delete property files
        sys.exit(0)

    issue_number = None
    for issue in gh_repo.get_issues(state="closed", labels=[str(label) for label in args.labels]):
        print("Issue already closed... Ready for building!")
        issue_number = issue.number

    if issue_number == None:
        print("Creating issue request...")
        issue_obj = gh_repo.create_issue(title=args.title, body=msg, labels=args.labels)
        issue_number = issue_obj.number
        print("New issue number: ", issue_number)

        pulls_curl = "curl -s 'https://api.github.com/repos/%s/issues?state=open&labels=%s'" % (
            args.repo,
            args.labels[0],
        )

        print("Checking existing PR with matching labels", pulls_curl)
        exit_code, pulls_obj = run_cmd(pulls_curl)
        pulls_obj = json.loads(pulls_obj)
        urls = ""
        for pull in pulls_obj:
            pull_obj = pull.get("pull_request")
            if pull_obj != None:
                urls += "* " + str(pull_obj.get("html_url")) + "\n"
        print("The following PRs have matching labels: \n", urls)

        # Comment related PRs
        if urls != "":
            issue_comment = (
                "The following PRs should be probably merged before building the new image: \n"
                + urls
            )
            print(issue_comment)
            create_issue_comment(gh_repo.full_name, issue_number, issue_comment)
    else:
        print("Ready for building!")
        # Process "building" or "queued" labels
        existing_labels = get_issue_labels(gh_repo.full_name, issue_number)
        print("Existing labels:", existing_labels)
        for label_obj in existing_labels:
            if "building" in label_obj["name"] or "queued" in label_obj["name"]:
                print("Build already triggered... Nothing to do!")
                with open("gh-info.tmp", "a") as f:
                    f.write(str(label_obj["name"]) + "\n")
        # Don't delete property files
        sys.exit(1)

    # Delete property files
    sys.exit(0)
else:
    for issue in gh_repo.get_issues(labels=[str(label) for label in args.labels]):
        issue_number = issue.number

    print("Adding issue comment...")
    create_issue_comment(gh_repo.full_name, issue_number, msg)
