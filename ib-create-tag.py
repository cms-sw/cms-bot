#!/usr/bin/env python
from __future__ import print_function

import datetime
import urllib.error
from os.path import dirname, abspath
from socket import setdefaulttimeout
from sys import argv

from cms_static import (
    GH_CMSSW_ORGANIZATION,
    GH_CMSSW_REPO,
)
from github_utils import (
    get_branch,
    get_git_tag,
    create_git_tag,
    get_commit_info,
    get_commit_tags,
)

setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(argv[0]))


if __name__ == "__main__":
    from optparse import OptionParser

    parser = OptionParser(
        usage="%prog [-n|--dry-run] [-N|--release-name] [-d|--day] [-H|--hour] [-b|--branch]"
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not modify Github",
        default=False,
    )
    parser.add_option(
        "-N",
        "--release-name",
        dest="release_name",
        action="store",
        help="CMSSW Release name",
    )
    parser.add_option("-d", "--day", dest="day", action="store", help="CMSSW IB day")
    parser.add_option("-H", "--hour", dest="hour", action="store", help="CMSSW IB hour")
    parser.add_option(
        "-b", "--branch", dest="branch", action="store", help="CMSSW branch"
    )
    parser.add_option(
        "-q", "--queue", dest="queue", action="store", help="CMSSW IB queue"
    )
    opts, args = parser.parse_args()

    RELEASE_NAME = opts.release_name  # "CMSSW_13_0_X_2023-02-02-1101"
    DAY = opts.day  # "02"
    HOUR = int(opts.hour)  # 11
    RELEASE_BRANCH = opts.branch  # "master"
    QUEUE = opts.queue  # "CMSSW_13_0_X"

    repo = "%s/%s" % (GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO)

    bran = get_branch(repo, RELEASE_BRANCH)
    try:
        ref = get_git_tag(repo, RELEASE_NAME)
        OLD_HASH = ref["object"]["sha"]
    except urllib.error.URLError:
        OLD_HASH = "X"

    head = bran["commit"]
    today = datetime.datetime.now().replace(
        hour=HOUR, minute=0, second=0, microsecond=0
    )
    head_time = datetime.datetime.strptime(
        head["commit"]["author"]["date"], "%Y-%m-%dT%H:%M:%SZ"
    )

    while head_time > today:
        try:
            head = head["parents"][0]
            info = get_commit_info(repo, head["sha"])
            head_time = datetime.datetime.strptime(
                info["author"]["date"], "%Y-%m-%dT%H:%M:%SZ"
            )
            head = info
        except IndexError:
            # No old-enough commits
            exit(1)

    NEW_HASH = head["sha"]

    if OLD_HASH == "X" and not opts.dryRun:
        create_git_tag(
            repo,
            RELEASE_NAME,
            NEW_HASH,
            "cmsbuild",
            "cmsbuild@cern.ch",
        )

    tags = get_commit_tags(repo, bran["commit"]["sha"])
    RELEASE_LIST = [t for t in tags if t.startswith(QUEUE + "_20")]
    print(" ".join(RELEASE_LIST))
