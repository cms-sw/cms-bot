#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser
from datetime import datetime
from socket import setdefaulttimeout

setdefaulttimeout(120)

if __name__ == "__main__":
    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    print("API Rate Limit")
    print("Limit, Remaining: ", gh.rate_limiting)
    print("Reset time (GMT): ", datetime.fromtimestamp(gh.rate_limiting_resettime))
