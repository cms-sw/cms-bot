#!/usr/bin/env python3
import re
import subprocess
from argparse import ArgumentParser
from os.path import dirname, abspath, join, exists
from socket import setdefaulttimeout

import github

from github_utils import api_rate_limits, get_gh_token, set_gh_user
from process_pr import (
    ISSUE_SEEN_MSG,
    CMSBOT_TECHNICAL_MSG,
    REGEX_COMMITS_CACHE,
    loads_maybe_decompress,
    process_pr,
)

setdefaulttimeout(120)
import sys

SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def load_bot_cache_local(comment_msg):
    seen_commits_match = REGEX_COMMITS_CACHE.search(comment_msg)
    if seen_commits_match:
        print("Loading bot cache")
        res = loads_maybe_decompress(seen_commits_match[1])
        return res
    return {}


def main():
    parser = ArgumentParser(usage="%prog <owner/repo>")
    parser.add_argument("-r", "--repository", dest="repository")
    parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true")
    args = parser.parse_args()

    repo_dir = join(SCRIPT_DIR, "repos", args.repository.replace("-", "_"))
    if exists(repo_dir):
        sys.path.insert(0, repo_dir)
    import repo_config

    cmsbuild_user = repo_config.CMSBUILD_USER
    set_gh_user(cmsbuild_user)

    if not getattr(repo_config, "RUN_DEFAULT_CMS_BOT", True):
        sys.exit(0)
    gh = github.Github(login_or_token=get_gh_token(args.repository))
    api_rate_limits(gh)
    repo = gh.get_repo(args.repository)

    cnt = 0

    with open("runme.sh", "w") as f:
        for issue in repo.get_issues(state="open", sort="updated", direction="desc"):
            print("Processing Issue#{0}: {1}".format(issue.number, issue.title))
            bot_cache = None
            for comment in issue.get_comments():
                if comment.user.login.encode("ascii", "ignore").decode() != cmsbuild_user:
                    continue
                comment_msg = (
                    comment.body.encode("ascii", "ignore").decode() if comment.body else ""
                )
                first_line = "".join(
                    [line.strip() for line in comment_msg.split("\n") if line.strip()][0:1]
                )
                if re.match(ISSUE_SEEN_MSG, first_line):
                    bot_cache = load_bot_cache_local(comment_msg)
                    print("Read bot cache from already seen comment:", comment)
                    break
                elif re.match(CMSBOT_TECHNICAL_MSG, first_line):
                    bot_cache = load_bot_cache_local(comment_msg)
                    print("Read bot cache from technical comment:", comment)
                    break
            if bot_cache and ("commits" not in bot_cache):
                print("Reprocessing PR")
                cnt += 1
                # Notice: can't "just" call process_pr, since it modifies global variables :(
                # process_pr(repo_config, gh, repo, issue, args.dryrun, cmsbuild_user=None, force=False)
                if not args.dryrun:
                    print(
                        "python3",
                        "process-pull-request.py",
                        "-n" if args.dryrun else "",
                        "-r",
                        args.repository,
                        file=f,
                    )

    api_rate_limits(gh)
    if args.dryrun:
        print(f"Would update {0} PRs/Issues".format(cnt))
    else:
        print(f"Updated {0} PRs/Issues".format(cnt))


if __name__ == "__main__":
    main()
