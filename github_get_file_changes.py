#!/usr/bin/env python
"""
This script will check what modules PR's are changing.
It assumes that a module is 2 directories deep ( dir1/dir2/)
and will ignore upper level files or directories.
"""

from __future__ import print_function
from github import Github
from github_utils import *
from os.path import expanduser
from repo_config import GH_TOKEN
from argparse import ArgumentParser
import json
from _py2with3compatibility import run_cmd
import logging
import os
import sys
from pprint import pformat

# logger and logger config
# https://docs.python.org/2/library/logger.html
FORMAT = '%(levelname)s - %(funcName)s - %(lineno)d: %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_changed_modules(filename_it):
    changed_m = set()
    for f_n in filename_it:
        s_l = f_n.split('/')
        if len(s_l) <= 2:
            # It is not a module, ignore
            pass
        else:
            changed_m.add(s_l[0] + "/" + s_l[1] + '/')
    return changed_m


def _get_unix_time(data_obj):
    return data_obj.strftime("%s")


def get_changed_filenames_by_pr(old_prs_dict, pr_list):
    """
    Returns union of all changed filenames by prs
    """
    changed_file_set = set()
    for pr in pr_list:
        # str(pr.number) because json.dump's dictonary keys as str even though they are int
        nr = str(pr.number)
        if nr in old_prs_dict.keys():  # TODO
            pr_old = old_prs_dict[nr]
            if int(_get_unix_time(pr.updated_at)) == pr_old['updated_at']:
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
        status, result = run_cmd('ls -1 -d */*/')  # only list directories 2 levels deep
    except Exception as e:
        logger.error("Error reading cloned repo files" + str(e))
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

    logger.debug(args.repo_name)
    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo_name)
    pr_list = get_pull_requests(repo)

    old_prs_dict = {}
    try:
        with open(args.cached_pr) as f:
            old_prs_dict = json.load(f)
    except Exception as e:
        print('Could not load a dumped prs', str(e))

    ch_f_set = get_changed_filenames_by_pr(old_prs_dict, pr_list)
    modules_mod_by_prs = get_changed_modules(ch_f_set)
    all_branch_modules = get_modules_with_mt(args.cloned_repo)  # TODO this will return folders 2 levels deep
    all_branch_modules_names = set([x[0] for x in all_branch_modules])

    new_files = []
    for changed_file in modules_mod_by_prs:
        if changed_file not in all_branch_modules_names:
            new_files.append(changed_file)
    if len(new_files) > 0:
        logger.debug("Changed file(s) not in the list:")
        logger.debug(pformat(new_files))

    non_changed_modules = all_branch_modules_names.difference(modules_mod_by_prs)
    # for m in cloned_mod:
    #     if m[0] not in modules_mod_by_prs:
    #         non_changed_modules.append(m)

    logger.debug("modules_mod_by_prs")
    logger.debug(pformat(modules_mod_by_prs))
    logger.debug("---")
    logger.debug("all_branch_modules")
    logger.debug(pformat(all_branch_modules))
    logger.debug("---")
    logger.debug("modules_mod_by_prs")
    logger.debug(pformat(modules_mod_by_prs))
    logger.debug("---")
    print(pformat("Modules modified by prs: {} \nAll modules: {} \nModules not touched by prs: {} \nNew files: {}".format(
        len(modules_mod_by_prs), len(all_branch_modules), len(non_changed_modules), len(new_files)))
    )


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
