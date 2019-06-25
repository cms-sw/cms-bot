#!/usr/bin/env python
"""
This script will check what modules PR's are changing.
It assumes that a module is 2 directories deep ( dir1/dir2/)
and will ignore upper level files or directories.
If no cached PRs directory is given, it will give all modules.
"""

from __future__ import print_function
from github import Github
from github_utils import *
from os.path import expanduser, exists
from repo_config import GH_TOKEN
from argparse import ArgumentParser
from glob import glob
import json
from _py2with3compatibility import run_cmd, cmp_f
from categories_map import CMSSW_CATEGORIES
import logging
import sys
from pprint import pformat

# logger and logger config
# https://docs.python.org/2/library/logger.html
FORMAT = '%(levelname)s - %(funcName)s - %(lineno)d: %(message)s'
logging.basicConfig(format=FORMAT)
logger = logging.getLogger(__name__)


def get_changed_modules(filename_it):
    changed_m = set()
    for f_n in filename_it:
        s_l = f_n.split('/')
        if len(s_l) <= 2:
            # It is not a module, ignore
            pass
        else:
            changed_m.add(s_l[0] + "/" + s_l[1])

    return changed_m


def get_changed_filenames_by_pr(old_prs_dict, pr_list):
    """
    Returns union of all changed filenames by prs
    """
    changed_file_set = set()
    for pr in pr_list:
        # str(pr.number) because json.dump's dictonary keys as str even though they are int
        nr = str(pr.number)
        if nr in old_prs_dict.keys():
            pr_old = old_prs_dict[nr]
            if int(get_unix_time(pr.updated_at)) == pr_old['updated_at']:
                changed_file_set = changed_file_set.union(pr_old['changed_files_names'])
                logger.debug("  Pr {} was cached".format(nr))
                continue  # we used cached files, ignore the rest of the loop

        # The PR is not cached or PR was updated
        changed_file_set = changed_file_set.union(pr_get_changed_files(pr))
        if nr in old_prs_dict.keys():
            logger.debug("! Pr {} cached, but needed to be updated.".format(nr))
        else:
            logger.debug("! Pr {} was not cached.".format(nr))

    return changed_file_set


def get_git_mt(path, filename):
    status, rez = run_cmd('cd %s; git log -1 --format="%%ad" --date=unix -- %s' % (path, filename))
    if status is not 0:
        print("ERROR, " + rez)
        sys.exit(1)  # todo throws an exception
    return rez


def get_modules_with_mt(path, depth=2):
    data_list = []
    unique_list = {}
    for l in ['/'.join(d.split('/')[-depth:]) for d in glob('%s/*/*' % path)]:
        if l in unique_list: continue
        data_list.append([l, get_git_mt(path, l)])
        unique_list[l] = 1
    return data_list


def main():
    parser = ArgumentParser()
    parser.add_argument("-n", "--repo_name", help="Repo name 'org/project")
    parser.add_argument("-c", "--cached_pr", default=None, help="Path to cached pr list")
    parser.add_argument("-r", "--cloned_repo", help="Path to cloned git repository")
    parser.add_argument("-l", "--logging", default="DEBUG", choices=logging._levelNames, help="Set level of logging")
    parser.add_argument("-o", "--output", default=None, help="Output result, which is a list of modules that are not"
                                                             " being modified by other PRs.")
    parser.add_argument("-i", "--ignore_modules", default=None, help="Ignore modules which are already done.")
    args = parser.parse_args()

    logger.setLevel(args.logging)
    logger.debug(args.repo_name)
    gh = Github(login_or_token=open(expanduser(GH_TOKEN)).read().strip())
    repo = gh.get_repo(args.repo_name)
    pr_list = get_pull_requests(repo, branch='master')
    logger.debug("GitHub API rate limit before: {}".format(gh.get_rate_limit()))

    all_branch_modules_w_mt = get_modules_with_mt(args.cloned_repo)  # this will return folders 2 levels deep
    all_branch_modules_names = set([x[0] for x in all_branch_modules_w_mt])
    modules_mod_by_prs = set()
    new_files = []  # new files introduced vy PRs
    if args.cached_pr:
        old_prs_dict = {}
        try:
            with open(args.cached_pr) as f:
                old_prs_dict = json.load(f)
        except Exception as e:
            print('Could not load a dumped prs', str(e))
            exit(1)
        ch_f_set = get_changed_filenames_by_pr(old_prs_dict, pr_list)
        modules_mod_by_prs = get_changed_modules(ch_f_set)

        for changed_file in modules_mod_by_prs:
            if changed_file not in all_branch_modules_names:
                new_files.append(changed_file)
        if len(new_files) > 0:
            logger.debug("Changed file(s) not in the list:")
            logger.debug(pformat(new_files))

    non_changed_modules = all_branch_modules_names.difference(modules_mod_by_prs)
    already_done_modules = set()
    if args.ignore_modules and exists(args.ignore_modules):
        already_done_modules = set(['/'.join(d.split('/')[-2:]) for d in glob('%s/*/*' % args.ignore_modules)])

    logger.debug("modules_mod_by_prs")
    logger.debug(pformat(modules_mod_by_prs))
    logger.debug("---")
    logger.debug("all_branch_modules_w_mt")
    logger.debug(pformat(all_branch_modules_w_mt))
    logger.debug("---")
    logger.debug("non_changed_module")
    logger.debug(pformat(non_changed_modules))
    logger.debug("---")
    print(pformat(
        "Modules modified by prs: {} \nAll modules: {} \nModules not touched by prs: {} \nNew modules: {}".format(
            len(modules_mod_by_prs), len(all_branch_modules_w_mt), len(non_changed_modules), len(new_files))
    ))

    unmodified_modules_sorted_by_time = [x for x in all_branch_modules_w_mt if
                                         (x[0] not in modules_mod_by_prs) and (x[0] not in already_done_modules)]
    unmodified_modules_sorted_by_time = sorted(unmodified_modules_sorted_by_time, cmp=lambda x, y: cmp_f(x[1], y[1]))

    logger.debug("Modules not modified by prs:")
    logger.debug(pformat(unmodified_modules_sorted_by_time))
    if args.output:
        package2categories = {}
        for cat in CMSSW_CATEGORIES:
            for pack in CMSSW_CATEGORIES[cat]:
                if pack not in package2categories:
                    package2categories[pack] = set([])
                package2categories[pack].add(cat)
        categories = {}
        for pack in package2categories:
            categories[pack] = "-".join(sorted(package2categories[pack]))
        with open(args.output, 'w') as f:
            for i in unmodified_modules_sorted_by_time:
                cat = categories[i[0]] if i[0] in categories else 'unknown'
                f.write("{} {}\n".format(cat, i[0]))
    logger.debug("GitHub API rate limit after: {}".format(gh.get_rate_limit()))


if __name__ == '__main__':
    main()
