#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser
from optparse import OptionParser
from datetime import datetime, timedelta
import re

if __name__ == "__main__":
    parser = OptionParser(usage="%prog <since-n-seconds>")
    parser.add_option("--repository", "-r", dest="repository", type=str, default="cms-sw/cmssw")
    parser.add_option(
        "--tests-pending",
        "-t",
        action="store_true",
        dest="only_tests_pending",
        help="Only show the pull requests that are pending for tests",
    )
    parser.add_option(
        "--only-issues",
        "-i",
        action="store_true",
        dest="only_issues",
        help="Only show actual issues",
    )

    opts, args = parser.parse_args()
    if not len(args):
        parser.error("Please specify the number of seconds since you want updates")

    since = datetime.utcnow() - timedelta(seconds=int(args[0]))
    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    repo = gh.get_repo(opts.repository)

    if opts.only_tests_pending:
        queried_labels = []
        queried_labels.append(repo.get_label("tests-pending"))
        issues = repo.get_issues(state="open", labels=queried_labels, sort="updated", since=since)
    else:
        label = [repo.get_label("release-build-request")]
        issues = repo.get_issues(state="open", sort="updated", since=since, labels=label)

    if opts.only_issues:
        issues = [i for i in issues if not i.pull_request]

    print(" ".join([str(x.number) for x in issues]))
