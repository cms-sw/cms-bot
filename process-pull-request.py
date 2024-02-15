#!/usr/bin/env python3
"""
Returns top commit of a PR (mostly used to comments)
"""
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import (
    api_rate_limits,
    get_pr_commits,
    get_pr_latest_commit,
    get_gh_token,
    enable_github_loggin,
)

setdefaulttimeout(120)
import sys

SCRIPT_DIR = dirname(abspath(sys.argv[0]))

if __name__ == "__main__":
    parser = OptionParser(usage="%prog <pull-request-id>")
    parser.add_option(
        "-c",
        "--commit",
        dest="commit",
        action="store_true",
        help="Get last commit of the PR",
        default=False,
    )
    parser.add_option(
        "-a",
        "--all",
        dest="all",
        action="store_true",
        help="Get all commits of the PR",
        default=False,
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
        "-f",
        "--force",
        dest="force",
        action="store_true",
        help="Force process the issue/PR even if it is ignored.",
        default=False,
    )
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="Enable debug logging in PyGithub",
        default=False,
    )
    opts, args = parser.parse_args()
    if opts.debug:
        enable_github_loggin()

    if len(args) != 1:
        parser.error("Too many/few arguments")
    prId = int(args[0])  # Positional argument is "Pull request ID"
    if opts.commit:
        if opts.all:
            for c in get_pr_commits(prId, opts.repository):
                print(c["sha"])
        else:
            print(get_pr_latest_commit(args[0], opts.repository))
    else:
        from github import Github

        repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
        if exists(repo_dir):
            sys.path.insert(0, repo_dir)
        import repo_config

        if not getattr(repo_config, "RUN_DEFAULT_CMS_BOT", True):
            sys.exit(0)
        gh = Github(login_or_token=get_gh_token(opts.repository), per_page=100)
        api_rate_limits(gh)
        repo = gh.get_repo(opts.repository)
        from process_pr import process_pr

        process_pr(repo_config, gh, repo, repo.get_issue(prId), opts.dryRun, force=opts.force)
        api_rate_limits(gh)
