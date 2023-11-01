#!/usr/bin/env python
from __future__ import print_function
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from datetime import datetime, timedelta
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from github_hooks_config import get_repository_hooks
import sys

setdefaulttimeout(None)
SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def check_prs(gh, repo, since, process_issue, dryRun):
    # if repo.full_name in ["cms-sw/cmsdist", "cms-sw/cmssw"]: return
    if not get_repository_hooks(repo.full_name, "Jenkins_Github_Hook"):
        return
    print("Working on Repository: ", repo.full_name)
    if since:
        issues = repo.get_issues(state="open", sort="updated", since=since)
    else:
        issues = repo.get_issues(state="open", sort="updated")
    err = 0
    for issue in issues:
        if not process_issue and not issue.pull_request:
            print("Only processing PRs, skipped issue: ", issue.number)
            continue
        try:
            process_pr(repo_config, gh, repo, issue, dryRun)
        except Exception as e:
            print("ERROR: Failed to process", repo.full_name, issue.number)
            print(e)
            err = 1
    return err


if __name__ == "__main__":
    parser = OptionParser(
        usage="%prog [-r|--repository <repo: default is cms-sw/cmssw>] [-i|--issue] [-s|--since <sec default is 3600>] [-n|--dry-run]"
    )
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not modify Github",
        default=False,
    )
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name, default is cms-sw/cmssw. Use 'externals' to process all external repos.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-s",
        "--since",
        dest="since",
        help="Pull request updated since time in sec",
        type="int",
        default=3600,
    )
    parser.add_option(
        "-i",
        "--issue",
        dest="issue",
        action="store_true",
        help="Process github issues",
        default=False,
    )
    opts, args = parser.parse_args()

    since = None
    if opts.since > 0:
        since = datetime.utcnow() - timedelta(seconds=opts.since)

    repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
    if exists(join(repo_dir, "repo_config.py")):
        sys.path.insert(0, repo_dir)
    import repo_config
    from process_pr import process_pr
    from categories import EXTERNAL_REPOS

    gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
    api_rate_limits(gh)
    repos = []
    if opts.repository != "externals":
        repos.append(opts.repository)
    else:
        repos = EXTERNAL_REPOS
    err = 0
    for repo_name in repos:
        if not "/" in repo_name:
            user = gh.get_user(repo_name)
            for repo in user.get_repos():
                err += check_prs(gh, repo, since, opts.issue, opts.dryRun)
        else:
            err += check_prs(gh, gh.get_repo(repo_name), since, opts.issue, opts.dryRun)
    sys.exit(err)
