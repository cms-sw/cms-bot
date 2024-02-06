#!/usr/bin/env python3
import re
import sys
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
)

setdefaulttimeout(120)

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
    parser.add_argument("-o", "--organization", dest="org", default="cms-sw")
    parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true")
    args = parser.parse_args()

    gh = github.Github(login_or_token=get_gh_token())
    api_rate_limits(gh)

    with open("runme.sh", "w") as f:
        gh_org = gh.get_organization(args.org)
        for repo in gh_org.get_repos():
            print("Using repository", repo.full_name)
            repo_name = repo.full_name
            repo_dir = join(SCRIPT_DIR, "repos", repo_name.replace("-", "_"))
            if exists(repo_dir):
                sys.path.insert(0, repo_dir)
            import repo_config

            cmsbuild_user = repo_config.CMSBUILD_USER
            set_gh_user(cmsbuild_user)

            if not getattr(repo_config, "RUN_DEFAULT_CMS_BOT", True):
                sys.exit(0)
            repo = gh.get_repo(repo_name)

            cnt = 0

            for issue in repo.get_issues():
                print("  Processing Issue#{0}: {1}".format(issue.number, issue.title))
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
                        print("    Read bot cache from already seen comment:", comment)
                        break
                    elif re.match(CMSBOT_TECHNICAL_MSG, first_line):
                        bot_cache = load_bot_cache_local(comment_msg)
                        print("    Read bot cache from technical comment:", comment)
                        break
                if bot_cache and ("commits" not in bot_cache):
                    print("    PR needs to be reprocessed")
                    cnt += 1
                    # Notice: can't "just" call process_pr, since it modifies global variables :(
                    # process_pr(repo_config, gh, repo, issue, args.dryrun, cmsbuild_user=None, force=False)
                    if not args.dryrun:
                        print(
                            "python3",
                            "process-pull-request.py",
                            "--force",
                            "--dry-run" if args.dryrun else "",
                            "--repository",
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
