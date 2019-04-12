#!/usr/bin/env python
"""
Gets list of files that will be modified by all PRs for the branch
"""

from github import Github
from github_utils import *
from os.path import expanduser
from repo_config import GH_TOKEN
from argparse import ArgumentParser
from _py2with3compatibility import run_cmd


def main():
    parser = ArgumentParser()
    parser.add_argument("-r", "--repo")
    parser.add_argument("-d", "--destination")
    parser.add_argument("-m", "--mode", type=int, default=1, choices=[1, 2])
    args = parser.parse_args()

    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo)
    pr_list = get_pull_requests(repo)
    fc_set = get_changed_files(pr_list)

    if args.mode == 1:
        with open(args.destination, 'w') as d:
            for f_name in fc_set:
                d.write(f_name + "\n")

    elif args.mode == 2:
        changed_modules_set = get_changed_modules(fc_set)
        with open(args.destination, 'w') as d:
            for f_name in changed_modules_set:
                d.write(f_name + "\n")


def get_changed_modules(filename_it):
    chanched_m = set()
    for f_n in filename_it:
        s_l = f_n.split('/')
        if len(s_l) <= 2:
            chanched_m.add(f_n)
        else:
            chanched_m.add(s_l[0] + "/" + s_l[1])
    return chanched_m


if __name__ == '__main__':
    main()
