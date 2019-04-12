#!/usr/bin/env python
"""

"""
from __future__ import print_function

import sys

from github import Github
from github_utils import *
from os.path import expanduser
from repo_config import GH_TOKEN
from argparse import ArgumentParser
import json
from _py2with3compatibility import run_cmd
import logging

path = '/tmp'
import os


def get_changed_modules(filename_it):
    chanched_m = set()
    for f_n in filename_it:
        s_l = f_n.split('/')
        if len(s_l) <= 2:
            chanched_m.add(f_n)
        else:
            chanched_m.add(s_l[0] + "/" + s_l[1])
    return chanched_m


def get_changed_filenames_by_pr(old_pr, pr_list):
    changed_file_set = set()
    for pr in pr_list:
        # str(pr.number) because json.dump's dictonary keys as str even though they are int
        nr = str(pr.number)
        if nr in old_pr.keys():  # TODo
            pr_old = old_pr[nr]
            if pr_old.updated_at == pr.updated_at:
                changed_file_set = changed_file_set.union(pr_old['changed_files_names'])
                pass
        else:
            changed_file_set = changed_file_set.union(pr_get_changed_files(pr))

    return changed_file_set


def get_git_mt(filename):
    status, rez = run_cmd('git log -1 --format="%ad" --date=unix -- ' + filename)
    if status is not 0:
        print("ERROR, " + rez)
        sys.exit(1)  # todo throws an exception
    return rez


def get_modules_with_mt(path):
    cwd = os.getcwd()
    try:
        os.chdir(path)
        status, result = run_cmd('ls -1 -d */*')  # only list directories 2 levels deep
    except Exception as e:
        logging.error("Error reading cloned repo files" + str(e))
        sys.exit(1)

    data_list = []
    for l in result.split('\n'):
        timestamp = get_git_mt(l)
        data_list.append([l, timestamp])

    os.chdir(cwd)
    return data_list


def main():
    parser = ArgumentParser()
    parser.add_argument("-n", "--repo_name", help="repo name 'org/project")
    parser.add_argument("-c", "--cached_pr", help="path to cached pr list")
    parser.add_argument("-r", "--cloned_repo", help="path to cloned git repository")
    args = parser.parse_args()

    logging.debug(args.repo_name)
    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo_name)
    pr_list = get_pull_requests(repo)

    old_pr = {}
    try:
        with open(args.cached_pr) as f:
            old_pr = json.load(f)
    except Exception as e:
        print('Could not load a dumped prs', str(e))
        import sys

    from pprint import pprint

    ch_f_set = get_changed_filenames_by_pr(old_pr, pr_list)
    modified_modules = get_changed_modules(ch_f_set)


    cloned_mod = get_modules_with_mt(args.cloned_repo)

    non_changed = []
    for m in cloned_mod:
        if m[0] not in modified_modules:
            non_changed.append(m)

    pprint(modified_modules)
    print("---")
    pprint(cloned_mod)
    print("---")
    pprint(modified_modules)
    print("---")

    pprint("mod: {} | all: {} | diff: {}".format(len(modified_modules), len(cloned_mod)), len(non_changed))


if __name__ == '__main__':
    main()

"""
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

"""
