#!/usr/bin/env python
from __future__ import print_function
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
        "-r",
        "--repository",
        dest="repo",
        help="Github repository e.g. cms-sw/cmssw",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-m",
        "--match",
        dest="match",
        help="Regexp to match tags e.g. CMSSW_8_0_X",
        type=str,
        default="CMSSW_.+",
    )
    opts, args = parser.parse_args()

    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    repo = gh.get_repo(opts.repo)
    print("API Rate Limit")
    print("Limit, Remaining: ", gh.rate_limiting)
    print("Reset time (GMT): ", datetime.fromtimestamp(gh.rate_limiting_resettime))

    tags = repo.get_releases()
    tagRe = re.compile("^" + opts.match + ".*$")
    for t in tags:
        if tagRe.match(t.name):
            print(t.name)
