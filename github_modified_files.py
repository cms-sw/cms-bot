#!/usr/bin/env python
"""
Gets list of files that will be modified by all PRs for the branch
"""

from github import Github
from github_utils import *
from os.path import expanduser
from repo_config import GH_TOKEN
from argparse import ArgumentParser
import json


def get_changed_modules(filename_it):
    chanched_m = set()
    for f_n in filename_it:
        s_l = f_n.split('/')
        if len(s_l) <= 2:
            chanched_m.add(f_n)
        else:
            chanched_m.add(s_l[0] + "/" + s_l[1])
    return chanched_m


def main():
    parser = ArgumentParser()
    parser.add_argument("-r", "--repo")
    parser.add_argument("-d", "--destination")
    parser.add_argument("-m", "--mode", type=int, default=1, choices=[1, 2, 3])
    args = parser.parse_args()

    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo)
    pr_list = get_pull_requests(repo)

    if args.mode == 1:
        rez = {}
        for pr in pr_list:
            rez[int(pr.number)] = {
                'number': int(pr.number),
                'state': pr.state,
                'created_at': int(pr.created_at.strftime("%s")),
                'updated_at': int(pr.updated_at.strftime("%s")),
                'changed_files_names': pr_get_changed_files(pr)
            }
        with open(args.destination, 'w') as d:
            json.dump(rez, d)

    elif args.mode == 2:
        fc_set = get_changed_files(pr_list)
        changed_modules_set = get_changed_modules(fc_set)
        with open(args.destination, 'w') as d:
            for f_name in changed_modules_set:
                d.write(f_name + "\n")

    elif args.mode == 3:
        fc_set = get_changed_files(pr_list)
        changed_modules_set = get_changed_modules(fc_set)
        with open(args.destination, 'w') as d:
            for f_name in changed_modules_set:
                d.write(f_name + "\n")


if __name__ == '__main__':
    main()
