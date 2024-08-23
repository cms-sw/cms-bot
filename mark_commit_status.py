#!/bin/bash

""":"
python_cmd="python"
python3 -V >/dev/null 2>&1 && python_cmd="python3"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function
from optparse import OptionParser
from github_utils import (
    api_rate_limits,
    mark_commit_status,
    get_combined_statuses,
    get_pr_latest_commit,
)
from sys import exit

if __name__ == "__main__":
    parser = OptionParser(usage="%prog")
    parser.add_option(
        "-c",
        "--commit",
        dest="commit",
        help="git commit for which set the status",
        type=str,
        default=None,
    )
    parser.add_option(
        "-p", "--pr", dest="pr", help="github pr for which set the status", type=str, default=None
    )
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-d",
        "--description",
        dest="description",
        help="Description of the status",
        type=str,
        default="Test running",
    )
    parser.add_option(
        "-C", "--context", dest="context", help="Status context", type=str, default="default"
    )
    parser.add_option("-u", "--url", dest="url", help="Status results URL", type=str, default="")
    parser.add_option(
        "-s",
        "--state",
        dest="state",
        help="State of the status e.g. pending, failure, error or success",
        type=str,
        default="pending",
    )
    parser.add_option(
        "-R",
        "--reset-all",
        dest="reset_all",
        help="Reset all matching contexts",
        action="store_true",
        default=False,
    )
    parser.add_option(
        "-e",
        "--if-exists",
        dest="if_exists",
        help="Only set the status if context already exists",
        action="store_true",
        default=False,
    )
    opts, args = parser.parse_args()

    if opts.pr:
        opts.commit = get_pr_latest_commit(opts.pr, opts.repository)
    if opts.if_exists:
        statues = get_combined_statuses(opts.commit, opts.repository)
        if "statuses" in statues:
            found = False
            for s in statues["statuses"]:
                if s["context"] != opts.context:
                    continue
                found = True
                break
            if not found:
                exit(0)
    mark_commit_status(
        opts.commit,
        opts.repository,
        opts.context,
        opts.state,
        opts.url,
        opts.description,
        reset=opts.reset_all,
    )
