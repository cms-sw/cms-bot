#!/usr/bin/env python3
"""
This script will test if there are other PRs that modify the same files.
This is primarily used to avoid merge conflicts.
"""

from __future__ import print_function
import json
import sys
if sys.version_info[0] == 2:
  from commands import getstatusoutput as run_cmd
else:
  from subprocess import getstatusoutput as run_cmd


def ascii_encode_dict(data):
    ascii_encode = lambda x: x.encode('ascii') if isinstance(x, unicode) else x
    return dict(map(ascii_encode, pair) for pair in data.items())


def build_open_file_list(prs_dict, branch):
    open_file_list = {}
    for pr in prs_dict:
        if prs_dict[pr]['base_branch'] == branch:
            for file in prs_dict[pr]['changed_files_names']:
                if open_file_list.has_key(file):
                    open_file_list[file].append(pr)
                else:
                    open_file_list[file] = [pr, ]

    return open_file_list


def check_pr_dict(prs_dict, prs_list, pr_number):
    for my_file in prs_dict[pr_number]['changed_files_names']:
        if len(prs_list[my_file]) > 1:
            print("File ", my_file, " modified in PR(s):", ', '.join(['#'+p  for p in  prs_list[my_file] if p!=pr_number]))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: SearchPROverlap.py <PR number> [ <branch> ]")
        print(
            "       <PR number>: number of PR belonging to <branch>, or \"all\" for loop on all open PRs in <branch>\n"
            "       If \"all\" is given as <PR number>, then a branch must be given as well.")
        exit()

    my_pr = sys.argv[1]
    my_branch = None
    e, o = run_cmd('curl -s -k -L https://raw.githubusercontent.com/cms-sw/cms-prs/master/cms-sw/cmssw/.other/files_changed_by_prs.json')
    prs_dict = json.loads(o)
    if my_pr not in prs_dict and not "all":
        print("PR # ", my_pr, "does not exists", file=sys.stderr)
        exit(1)
    if len(sys.argv) > 2:
        my_branch = sys.argv[2]
    elif len(sys.argv) == 2 and my_pr == 'all':
        print("ERROR: If \"all\" is given as <PR number>, then a branch must be given as well.")
        exit(1)
    else:
        pr_metadata = prs_dict[my_pr]
        my_branch = pr_metadata['base_branch']
    my_list = build_open_file_list(prs_dict, my_branch)

    if my_pr == "all":
        for pr in prs_dict:
            if prs_dict[pr]['base_branch'] == my_branch:
                check_pr_dict(prs_dict, my_list, pr)
    else:
        if prs_dict[my_pr]['base_branch'] != my_branch:
            print("PR # ", my_pr, " not belonging to branch ", my_branch, file=sys.stderr)
            exit(1)
        else:
            check_pr_dict(prs_dict, my_list, my_pr)
