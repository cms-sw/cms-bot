#!/usr/bin/env python3
import re
import sys
from argparse import ArgumentParser
from os.path import dirname, abspath, join, exists
from socket import setdefaulttimeout

import github

from cms_static import VALID_CMS_SW_REPOS_FOR_TESTS
from github_utils import api_rate_limits, get_gh_token, set_gh_user
from process_pr import (
    ISSUE_SEEN_MSG,
    CMSBOT_TECHNICAL_MSG,
    REGEX_COMMITS_CACHE,
    loads_maybe_decompress,
)

# Copied from gh-teams.py
CMS_ORGANIZATIONS = ["cms-data", "cms-externals", "cms-sw"]

setdefaulttimeout(120)

SCRIPT_DIR = dirname(abspath(sys.argv[0]))


# Notice: can't use `process_pr.read_bot_cache` since it modifies bot cache before returning.
# Another solution is to add a flag to `read_bot_cache` to load cache without adding missing keys
def load_bot_cache_local(comment_msg):
    seen_commits_match = REGEX_COMMITS_CACHE.search(comment_msg)
    if seen_commits_match:
        print("Loading bot cache")
        res = loads_maybe_decompress(seen_commits_match[1])
        return res
    return {}


def process_repo(gh, repo, args):
    res = []
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

    for issue in repo.get_pulls(sort="updated", direction="desc", state="all"):
        print("  Processing PR#{0}: {1}".format(issue.number, issue.title))
        api_rate_limits(gh)
        bot_cache = None
        for comment in issue.get_issue_comments():
            if comment.user.login.encode("ascii", "ignore").decode() != cmsbuild_user:
                continue
            comment_msg = comment.body.encode("ascii", "ignore").decode() if comment.body else ""
            first_line = "".join(
                [line.strip() for line in comment_msg.split("\n") if line.strip()][0:1]
            )
            if re.match(CMSBOT_TECHNICAL_MSG, first_line):
                bot_cache = load_bot_cache_local(comment_msg)
                if bot_cache:
                    print("    Read bot cache from already seen comment:", comment)
                    break
            elif re.match(ISSUE_SEEN_MSG, first_line):
                bot_cache = load_bot_cache_local(comment_msg)
                if bot_cache:
                    print("    Read bot cache from technical comment:", comment)
                    break
        if bot_cache and ("commits" not in bot_cache):
            print("    PR needs to be reprocessed")
            # Notice: can't "just" call process_pr, since it modifies global variables :(
            # process_pr(repo_config, gh, repo, issue, args.dryrun, cmsbuild_user=None, force=False)
            res.append(
                "python3 process-pull-request.py --force "
                + (" --dry-run " if args.dryrun else " ")
                + "--repository "
                + repo.full_name
                + " "
                + str(issue.number)
            )

        if not bot_cache:
            print("No bot cache, stopping here")
            break

    return res


def main():
    parser = ArgumentParser()
    parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true")
    args = parser.parse_args()

    gh = github.Github(login_or_token=get_gh_token())
    api_rate_limits(gh)
    cnt = 0

    all_repos = []

    for name in VALID_CMS_SW_REPOS_FOR_TESTS:
        all_repos.append("cms-sw/" + name)

    for org in CMS_ORGANIZATIONS:
        if org == "cms-sw":
            continue

        all_repos.extend(r.full_name for r in gh.get_organization(org).get_repos())

    with open("runme.sh", "w") as f:
        for repo_name in all_repos:
            print("Getting repo", repo_name)
            try:
                repo = gh.get_repo(repo_name)
            except github.UnknownObjectException:
                continue
            res = process_repo(gh, repo, args)
            print("Writing {0} line(s) to script".format(len(res)))
            for line in res:
                print(line, file=f)

            cnt += len(res)

    if args.dryrun:
        print("Would update {0} PRs/Issues".format(cnt))
    else:
        print("Updated {0} PRs/Issues".format(cnt))


if __name__ == "__main__":
    main()
