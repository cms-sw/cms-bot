#!/bin/bash

""":"
python_cmd="python3"
python -V >/dev/null 2>&1 && python_cmd="python"
exec ${python_cmd} $0 ${1+"$@"}
"""

from __future__ import print_function

import datetime
import time
from _py2with3compatibility import HTTPError
from os.path import dirname, abspath
from socket import setdefaulttimeout
import sys

from cms_static import (
    GH_CMSSW_ORGANIZATION,
    GH_CMSSW_REPO,
)
from github_utils import (
    get_git_tag,
    create_git_tag,
    get_commits,
    find_tags,
)

from categories import CMSSW_ORP

setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def currenttz():
    tm = time.localtime()
    return datetime.timezone(datetime.timedelta(seconds=tm.tm_gmtoff), tm.tm_zone)


IBS_WITH_HEAD_COMMITS = ["CMSSW_5_3_HI_X"]
MAX_RETRY_COUNT = 5  # Try resolving git tag at most this number of times
RETRY_DELAY = 10  # Delay (in s) between retries

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
    parser.add_option(
        "-d", "--date", dest="date", action="store", help="CMSSW IB date (YYYY-MM-DD)"
    )
    parser.add_option("-H", "--hour", dest="hour", action="store", help="CMSSW IB hour (HH)")
    parser.add_option(
        "-M", "--minute", dest="minute", action="store", help="CMSSW IB minute (MM)", default="00"
    )
    parser.add_option("-b", "--branch", dest="branch", action="store", help="CMSSW branch")
    parser.add_option("-q", "--queue", dest="queue", action="store", help="CMSSW IB queue")
    opts, args = parser.parse_args()

    RELEASE_NAME = opts.release_name  # "CMSSW_13_0_X_2023-02-02-1100"
    ib_date = (
        datetime.datetime.strptime(
            "%s %s:%s" % (opts.date, opts.hour, opts.minute), "%Y-%m-%d %H:%M"
        )
        .replace(tzinfo=currenttz())
        .astimezone(datetime.timezone.utc)
    )

    RELEASE_BRANCH = opts.branch  # "master"
    QUEUE = opts.queue  # "CMSSW_13_0_X"

    repo = "%s/%s" % (GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO)
    commit_url = "https://api.github.com/repos/%s/commits/" % repo

    for _ in range(MAX_RETRY_COUNT):
        HEAD_SHA = None
        try:
            ref = get_git_tag(repo, RELEASE_NAME)
            HEAD_SHA = ref["object"]["sha"]
        except HTTPError as e1:
            if e1.code != 404:
                error_body = e1.read().decode("ascii", errors="replace")
                print(
                    "Unexpected HTTPError when calling get_git_tag: {0}\nResponse: {1}".format(
                        e1, error_body
                    ),
                    file=sys.stderr,
                )
            else:
                commits_ = get_commits(repo, RELEASE_BRANCH, until=ib_date, per_page=100)
                if not commits_:
                    print("get_commits failed", file=sys.stderr)
                    sys.exit(1)

                head = None
                for commit_ in commits_:
                    if (len(commit_["parents"]) == 1) and (not QUEUE in IBS_WITH_HEAD_COMMITS):
                        continue
                    if commit_["url"].startswith(commit_url):
                        head = commit_
                        break

                if head is None:
                    sys.exit(1)

                HEAD_SHA = head["sha"]
                if not opts.dryRun:
                    try:
                        create_git_tag(
                            repo,
                            RELEASE_NAME,
                            HEAD_SHA,
                        )
                    except HTTPError as e:
                        HEAD_SHA = None
                        error_body = e.read().decode("ascii", errors="replace")
                        if not (e.code == 422 and "already exists" in error_body.lower()):
                            print(
                                "Unexpected HTTPError when creating git reference: {0}\nResponse: {1}".format(
                                    e, error_body
                                ),
                                file=sys.stderr,
                            )
                else:
                    print("Tag head: ", HEAD_SHA)

        if HEAD_SHA is None:
            time.sleep(RETRY_DELAY)
        else:
            break

    if HEAD_SHA is None:
        print(
            "Could not get HEAD_SHA after {0} retries, quitting".format(MAX_RETRY_COUNT),
            file=sys.stderr,
        )
        sys.exit(1)

    tags = find_tags(repo, QUEUE + "_20")
    RELEASE_LIST = [
        t["ref"].replace("refs/tags/", "") for t in tags if t["object"]["sha"] == HEAD_SHA
    ]
    print(" ".join(RELEASE_LIST[::-1]))
