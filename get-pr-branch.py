#!/usr/bin/env python3
"""
Get the branch of pull request. It was made in mind that it will be used to get branch-name for CMSSW repo.

Arguments:
argv[1] - Pull request ID
argv[2] - Repository (optional)
"""

from sys import exit, argv, path
from os.path import expanduser, dirname, abspath, join, exists
from socket import setdefaulttimeout
from github_utils import get_pr

setdefaulttimeout(120)

if __name__ == "__main__":
    prId = int(argv[1])
    repo = "cms-sw/cmssw"
    try:
        repo = argv[2]
    except IndexError:
        pass

    try:
        pr = get_pr(repo, prId)
    except Exception as ex:
        print("Could not find pull request %s. Maybe this is an issue" % prId)
        print(ex)
        exit(1)

    if pr["base"]["ref"] == "master":
        from releases import CMSSW_DEVEL_BRANCH
        from _py2with3compatibility import run_cmd

        e, o = run_cmd(
            "curl -k -s -L https://cmssdt.cern.ch/SDT/BaselineDevRelease | grep '^CMSSW_'"
        )
        if not o:
            o = CMSSW_DEVEL_BRANCH
        print(o)
    else:
        pr_branch = pr["base"]["ref"]
        try:
            SCRIPT_DIR = dirname(abspath(argv[0]))
            repo_dir = join(SCRIPT_DIR, "repos", repo.replace("-", "_"))
            if exists(join(repo_dir, "repo_config.py")):
                path.insert(0, repo_dir)
                import repo_config

                pr_branch = repo_config.CMS_BRANCH_MAP[pr["base"]["ref"]]
        except KeyError:
            pass
        print(pr_branch)
