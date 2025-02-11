#!/usr/bin/env python3
"""
Returns top commit of a PR (mostly used to comments)
"""
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout
from github_utils import (
    api_rate_limits,
    get_gh_token,
    set_gh_user,
)

setdefaulttimeout(120)
import sys, json, re
from github import Github

SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def process_issue_comment(payload, repo_config, gh, dryRun):
    if not "pull_request" in payload["issue"]:
        print("WARNING: comment is made on a GH issue")
        return
    if not payload["action"] in ["created"]:
        print("WARNING: Unknown action %s" % payload["action"])
        return
    cobj = payload["comment"]
    comment = cobj["body"].strip().split("\n")
    if not re.match("^((@*cmsbot(,\s*|\s+))|)please\s+(run\s+|)test$", comment[0], re.I):
        print("Unknown comment first line: %s" % comment[0])
        return
    commentor = cobj["user"]["login"]
    print("Test requested by %s at %s" % (commentor, cobj["created_at"]))
    repo_owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["full_name"]
    repo = gh.get_repo(repo_name)
    prId = payload["issue"]["number"]
    issue = repo.get_issue(prId)
    gh_comment = issue.get_comment(cobj["id"])
    from process_pr import set_emoji, create_property_file

    if not commentor in repo_config.TRIGGER_PR_TESTS + [repo_owner]:
        print("Not an authorized user to trigger test")
        if not dryRun:
            set_emoji(repo, gh_comment, "-1", True)
        return
    print("Starting Tests")
    if not dryRun:
        set_emoji(repo, gh_comment, "+1", True)
    parameters = {"PULL_REQUEST": prId, "REPOSITORY": repo_name, "REQUESTOR": commentor}
    try:
        parameters["BOT_JOB_NAME"] = repo_config.BOT_JOB_NAME
    except:
        parameters["BOT_JOB_NAME"] = "pr-test-%s" % repo_name.replace("/", "-")
    create_property_file("simple-cms-bot-pr-test-%s.properties" % prId, parameters, dryRun)
    return


if __name__ == "__main__":
    parser = OptionParser(usage="%prog")
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not modify Github",
        default=False,
    )
    parser.add_option(
        "-e",
        "--event",
        dest="event",
        help="Type of github webhook event e.g. issue_comment",
        type=str,
        default="",
    )

    opts, args = parser.parse_args()
    if len(args) != 0:
        parser.error("Too many")
    if not opts.event in ["issue_comment"]:
        print("ERROR: Event %s not recognized" % opts.event)
        sys.exit(0)

    payload = json.load(sys.stdin)
    repo_name = payload["repository"]["full_name"]
    repo_dir = join(SCRIPT_DIR, "repos", repo_name.replace("-", "_"))
    if exists(repo_dir):
        sys.path.insert(0, repo_dir)
        print("Reading ", repo_dir)
    import repo_config

    set_gh_user(repo_config.CMSBUILD_USER)
    gh = Github(login_or_token=get_gh_token(repo_name), per_page=100)
    api_rate_limits(gh)
    process_issue_comment(payload, repo_config, gh, opts.dryRun)
    api_rate_limits(gh)
