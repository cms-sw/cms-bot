#!/usr/bin/env python3
from __future__ import print_function
from github import Github
from os.path import expanduser
from repo_config import GH_TOKEN


def main():
    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    print("GitHub API rate limit: {0}".format(gh.get_rate_limit()))


if __name__ == '__main__':
    main()
