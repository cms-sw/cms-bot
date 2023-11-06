#!/usr/bin/env python3
# test commit
from github import Github, GithubException
from os.path import expanduser
from optparse import OptionParser
from datetime import datetime
from sys import exit
import re
from socket import setdefaulttimeout

setdefaulttimeout(120)

if __name__ == "__main__":
    parser = OptionParser(
        usage="%prog -b|--branch <branch> -d|--date <YYYY-MM-DD-HH00> -t|--tag <tag> [-n|--dry-run]"
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        help="Do not modify Github",
        default=False,
        action="store_true",
    )
    parser.add_option(
        "-b",
        "--branch",
        dest="branch",
        help="Repository branch to use for tagging e.g CMSSW_8_0_X",
        type=str,
        default=None,
    )
    parser.add_option(
        "-d",
        "--date",
        dest="date",
        help="Date/time to search for the commit to tag e.g. 2015-10-19-1100",
        type=str,
        default=None,
    )
    parser.add_option(
        "-t",
        "--tag",
        dest="tag",
        help="Tag of the IB e.g. CMSSW_8_0_X_2015-10-19-1100. Default is <Branch>_<YYYY-MM-DD-HH00>",
        type=str,
        default=None,
    )
    opts, args = parser.parse_args()

    if not opts.branch:
        parser.error("Missing branch argument -b|--branch <Branch>")
    if not opts.date:
        parser.error("Missing date argument -d|--date <YYYY-MM-DDTHH00>")

    commit_date = datetime.strptime(opts.date, "%Y-%m-%d-%H00")
    if not opts.tag:
        opts.tag = opts.branch + "_" + commit_date.strftime("%Y-%m-%d-%H00")

    commit_date = commit_date - (datetime.now() - datetime.utcnow())

    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    rate_limit = gh.get_rate_limit().rate
    print("API Rate Limit")
    print("Limit: ", rate_limit.limit)
    print("Remaining: ", rate_limit.remaining)
    print("Reset time (GMT): ", rate_limit.reset)

    repo = gh.get_repo("cms-sw/cmssw")
    commits = repo.get_commits(sha=opts.branch, until=commit_date)
    last_merge = None
    for c in commits:
        if c.parents:
            last_merge = c
            break
    sha = last_merge.sha
    print("Found Commit :", sha, last_merge.author.login, "(", last_merge.author.name, ")")
    if not opts.dryRun:
        try:
            repo.create_git_tag(opts.tag, "Release", sha, "commit")
            repo.create_git_ref("refs/tags/" + opts.tag, sha)
            print("Created Tag ", opts.tag, " based on ", sha)
        except GithubException as e:
            msg = e.data["message"].encode("ascii", "ignore").decode()
            print("Message: ", msg)
            if re.match("^.*Reference already exists.*$", msg, re.M):
                exit(0)
            print("ERROR: unable to create tag ", opts.tag)
            exit(1)
    else:
        print("Dry run, would have created tag ", opts.tag, " based on ", sha)
    exit(0)
