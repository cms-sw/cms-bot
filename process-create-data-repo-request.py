#!/usr/bin/env python3
import re
from datetime import datetime
from optparse import OptionParser
from os.path import expanduser
from socket import setdefaulttimeout
from typing import Optional, Any

import github
from github import Github

from categories_map import CMSSW_CATEGORIES
from cms_static import (
    GH_CMSSW_REPO,
    CREATE_REPO,
    GH_CMSSW_ORGANIZATION,
)
from github_utils import api_rate_limits

setdefaulttimeout(120)


# Processes a github issue to check if it is requesting the creation of a new data repo
# If the issue is not requesting new repo, it ignores it.

# -------------------------------------------------------------------------------
# Global Variables
# --------------------------------------------------------------------------------

opts: Optional[Any] = None
labels = []

INVALID_REQUEST_MSG = "No category found for requested package {package}"
EXISTS_MSG = "Requested repository {repo} already exists"
ACK_MSG = (
    "Request received. I will create the requested repository after this issue is fully signed."
)
COMPLETE_MSG = "Repository created: {url}"

# -------------------------------------------------------------------------------
# Statuses
# --------------------------------------------------------------------------------
# This is to determine the status of the issue after reading the labels

# Default state
NEW_ISSUE = "new-issue"
# The issue is pending assignment
PENDING_ASSIGNMENT = "pending-assignment"
# The issue has been received, but it needs approval to start the build
PENDING_APPROVAL = "pending-approval"
# The build has been queued in jenkins
FULLY_SIGNED = "fully-signed"

# -------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------


#
# Searches in the comments if there is a comment made from  the given users  that
# matches the given pattern. It returns a list with the matched comments.
#
def search_in_comments(comments, user_logins, pattern, first_line):
    found_comments = []
    requested_comment_bodies = [c.body for c in comments if c.user.login in user_logins]
    for body in requested_comment_bodies:
        examined_str = body
        if first_line:
            examined_str = str(
                body.encode("ascii", "ignore").decode().split("\n")[0].strip("\n\t\r ")
            )

        if examined_str == pattern:
            found_comments.append(body)
            continue

        if re.match(pattern, examined_str):
            found_comments.append(body)

    return found_comments


#
# posts a message to the issue in github
# if dry-run is selected it doesn't post the message and just prints it
# if you set checkIfRepeated to False, if will not check if the message has already been written.
#
def post_message(issue, msg, comments, checkIfRepeated=True):
    if checkIfRepeated and search_in_comments(comments, ["cmsbuild"], msg, False):
        print("Message already in the thread: \n %s" % msg)
        return

    if opts.dryRun:
        print("Not posting message (dry-run):\n %s" % msg)
        return

    print("Posting message:\n %s" % msg)
    issue.create_comment(msg)


#
# reads the comments and gets returns the status of the issue
#
def get_issue_status(issue):
    global labels
    labels = [label.name for label in issue.get_labels()]
    print("Issue Label: ", labels)

    if PENDING_ASSIGNMENT in labels:
        return PENDING_ASSIGNMENT
    if any(label.endswith("-pending") for label in labels):
        return PENDING_APPROVAL
    if FULLY_SIGNED in labels:
        return FULLY_SIGNED

    return NEW_ISSUE


#
# closes the issue
#
def close_issue(issue):
    if opts.dryRun:
        print("Not closing issue (dry-run)")
        return
    print("Closing issue...")
    issue.edit(state="closed")


# -------------------------------------------------------------------------------
# Start of execution
# --------------------------------------------------------------------------------


def main():
    global opts, PENDING_APPROVAL
    parser = OptionParser(usage="%prog <issue-id>")
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not post on Github",
        default=False,
    )
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        parser.error("Too many arguments")

    GH_TOKEN = open(expanduser("~/.github-token")).read().strip()

    issue_id = int(args[0])
    gh = Github(login_or_token=GH_TOKEN)
    api_rate_limits(gh)
    cmssw_repo_name = GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO
    cmssw_repo = gh.get_repo(cmssw_repo_name)
    issue = cmssw_repo.get_issue(issue_id)
    print("API Rate Limit")
    print("Limit, Remaining: ", gh.rate_limiting)
    print("Reset time (GMT): ", datetime.fromtimestamp(gh.rate_limiting_resettime))

    # 0. Is this issue closed?
    if issue.state == "closed":
        print("Issue closed, ignoring.")
        exit(0)

    # 1. Is this a pull request?
    if issue.pull_request:
        print("This is a pull request, ignoring.")
        exit(0)

    title_match = re.match(CREATE_REPO, issue.title)

    # 2. Is this issue meant to create a new cms-data repo?
    if not title_match:
        print("This issue is not for creating a repo, ignoring.")
        print(issue.title)
        exit(0)

    category_name = title_match.group(1)
    package_name = title_match.group(2)

    print(category_name + "/" + package_name)

    # 3. Does the requested repository already exist?
    repo = None
    try:
        repo = gh.get_organization("cms-data").get_repo(category_name + "-" + package_name)
    except github.UnknownObjectException:
        pass

    comments = [c for c in issue.get_comments()]

    if repo:
        post_message(issue, EXISTS_MSG.format(repo=repo.url), comments)
        close_issue(issue)
        exit(0)

    # Figure out who must approve the action
    data_categs = set()
    for cat, pkgs in CMSSW_CATEGORIES.items():
        for pkg in pkgs:
            if not pkg:
                continue
            if re.match(pkg + ".*", category_name + "/" + package_name):
                data_categs.add(cat)
                break

    data_categs = sorted(list(data_categs))
    print(data_categs)

    if not data_categs:
        post_message(
            issue,
            INVALID_REQUEST_MSG.format(package=category_name + "/" + package_name),
            comments,
        )
        exit(0)

    # Get the status of this issue.
    status = get_issue_status(issue)
    print("Status: %s \n" % status)
    print("Issue labels:", labels)

    if status == NEW_ISSUE:
        print("Issue not processed by the cms-bot yet, skipping")
        exit(0)

    if status == PENDING_ASSIGNMENT:
        post_message(issue, "assign " + ",".join(data_categs), comments)
        post_message(issue, ACK_MSG, comments)
        if not opts.dryRun:
            issue.create_reaction("+1")
        exit(0)

    if status == PENDING_APPROVAL:
        print("Request not approved yet")
        exit(0)

    if status == FULLY_SIGNED:
        org = gh.get_organization("cms-data")
        if not opts.dryRun:
            new_repo = org.create_repo(
                category_name + "-" + package_name,
                "Data files for " + category_name + "/" + package_name,
                has_wiki=False,
                has_projects=False,
                private=False,
                auto_init=True,
            )

            with open("new-repo.txt", "w") as out:
                out.write("REPOSITORY=cms-data/%s-%s\n" % (category_name, package_name))
            post_message(issue, COMPLETE_MSG.format(url=new_repo.html_url), comments)
            close_issue(issue)
        else:
            print("(Dry-run) Not creating repo ", category_name + "-" + package_name)
            exit(0)


if __name__ == "__main__":
    main()
