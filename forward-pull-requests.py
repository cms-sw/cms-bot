#!/usr/bin/env python3

# Given a branch, gets all of its pull requests
# and recreates them in a different branch.

from __future__ import print_function
from github import Github, GithubException
from sys import exit
from os.path import expanduser
from argparse import ArgumentParser
from datetime import datetime
from _py2with3compatibility import Request, urlopen
from time import sleep
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from github_utils import get_ported_PRs
from socket import setdefaulttimeout

setdefaulttimeout(120)
import json

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--source")
    parser.add_argument("-d", "--dest")
    parser.add_argument(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default=gh_user + "/" + gh_cmssw,
    )
    parser.add_argument("--since", dest="since", default=None)
    parser.add_argument("-n", "-dry-run", dest="dryRun", default=False, action="store_true")
    parser.add_argument("pulls", nargs="*", type=int)
    args = parser.parse_args()

    print(args)
    if args.source == args.dest:
        print("Source and destination branches are same")
        exit(1)
    elif (not args.source) or (not args.dest):
        print("Missing source or destination branch")
        exit(1)

    since = datetime(2000, 1, 1)
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%dT%H:%M")
    GH_TOKEN = open(expanduser("~/.github-token")).read().strip()
    gh = Github(login_or_token=GH_TOKEN)

    try:
        gh_repo = gh.get_repo(args.repository)
    except:
        print("Could not find repository.")
        exit(1)

    gh_repo.get_branch(args.source)
    gh_repo.get_branch(args.dest)

    pulls = args.pulls or gh_repo.get_pulls(base=args.source, state="open")

    done_prs_id = get_ported_PRs(gh_repo, args.source, args.dest)
    for pr in pulls:
        # If we just have the numeric Id, let's get the associated issue.
        if type(pr) == int:
            pr = gh_repo.get_pull(pr)
        print("Checking ", pr.number)
        if pr.number in done_prs_id:
            print("Already ported as #", done_prs_id[pr.number])
            continue
        if pr.created_at < since:
            print("Older than ", args.since)
            continue
        print(pr.number, pr.head.user.login, pr.head.ref, pr.created_at)
        newBody = (
            pr.body
            + "\nAutomatically ported from "
            + args.source
            + " #%s (original by @%s).\nPlease wait for a new IB (12 to 24H) before requesting to test this PR."
            % (pr.number, str(pr.head.user.login))
        )
        try:
            newHead = "%s:%s" % (pr.head.user.login, pr.head.ref)
            print("-----")
            print("Porting %s" % pr.number)
            print(pr.title)
            print(newBody)
            print(args.dest)
            print(newHead)
            print("---")
            if args.dryRun:
                print("ATTENTION: Not creating new PR on Github (dry-run)")
                continue
            params = {
                "title": pr.title,
                "body": newBody,
                "head": newHead,
                "base": args.dest,
                "maintainer_can_modify": False,
            }
            request = Request(
                "https://api.github.com/repos/cms-sw/cmssw/pulls",
                headers={"Authorization": "token " + GH_TOKEN},
            )
            request.get_method = lambda: "POST"
            newPR = json.loads(urlopen(request, json.dumps(params).encode()).read())
            print("New PR number", newPR["number"])
            sleep(15)
        except GithubException as e:
            print("Error while processing: ", pr.number)
            print(e)
            continue
