#!/usr/bin/env python3
"""
Returns top commit of a PR (mostly used to comments)
"""
import argparse
from os.path import dirname, abspath, join, exists
from socket import setdefaulttimeout

from github_utils import (
    api_rate_limits,
    get_gh_token,
    enable_github_loggin,
)

from process_pr_v2 import process_pr

setdefaulttimeout(120)
import sys

SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process a GitHub pull request via cms-bot tooling."
    )

    parser.add_argument("pr_id", type=int, help="Pull request ID")

    # Flags
    parser.add_argument(
        "-c",
        "--commit",
        action="store_true",
        help="Print last commit of the PR instead of processing the PR.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Print all commits of the PR (used with --commit).",
    )
    parser.add_argument("-n", "--dry-run", action="store_true", help="Do not modify GitHub.")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force processing even if PR/issue would normally be ignored.",
    )
    parser.add_argument(
        "-r", "--repository", default="cms-sw/cmssw", help="GitHub repository (e.g. cms-sw/cmssw)."
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging in PyGithub."
    )

    return parser.parse_args()


def main():
    opts = parse_args()

    if opts.debug:
        enable_github_loggin()

    pr_id = opts.pr_id

    # --- Commit listing mode ---
    if opts.commit:
        if opts.all:
            for c in get_pr_commits(pr_id, opts.repository):
                print(c["sha"])
        else:
            print(get_pr_latest_commit(pr_id, opts.repository))
        return

    # --- Full PR processing mode ---
    repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
    if exists(repo_dir):
        sys.path.insert(0, repo_dir)

    import repo_config

    if not getattr(repo_config, "RUN_DEFAULT_CMS_BOT", True):
        return
    if getattr(repo_config, "REQUEST_PROCESSOR", "cms-bot") != "cms-bot":
        return

    gh = Github(login_or_token=get_gh_token(opts.repository), per_page=100)
    api_rate_limits(gh)

    repo = gh.get_repo(opts.repository)
    process_pr(repo_config, gh, repo, repo.get_issue(pr_id), opts.dry_run, force=opts.force)

    api_rate_limits(gh)


if __name__ == "__main__":
    main()
