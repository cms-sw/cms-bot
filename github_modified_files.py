#!/usr/bin/env python
"""
Writes all change files for a file
"""

from github import Github
from github_utils import *
from os.path import expanduser
from repo_config import GH_TOKEN
from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument("-r", "--repo")
    parser.add_argument("-d", "--destination")
    args = parser.parse_args()

    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo)
    pr_list = get_pull_requests(repo)
    fc_set = get_changed_files(pr_list)

    with open(args.destination, 'w') as d:
        for f_name in fc_set:
            d.write(f_name + "\n")


if __name__ == '__main__':
    main()