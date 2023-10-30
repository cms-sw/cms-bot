#!/usr/bin/env python3
import sys
from sys import exit, argv
from re import match
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
from socket import setdefaulttimeout

setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(argv[0]))


def mark_pr_ready_for_test(repo, pr, context="cmsbot/test"):
    try:
        latest_commit = pr.get_commits().reversed[0].sha  # Get the latest commit SHA
        repo.get_commit(latest_commit).create_status(
            state="success", context=context, description="Ready for testing"
        )
        print("Commit status marked as 'Ready for testing'")
    except GithubException as e:
        print(f"Failed to mark commit status: {e}")


def process_pr(gh, repo, issue, dryRun):
    from cmsdist_merge_permissions import USERS_TO_TRIGGER_HOOKS, getCommentCommand, hasRights

    print("Issue state:", issue.state)
    prId = issue.number
    pr = None
    branch = None
    cmdType = None
    chg_files = []
    if issue.pull_request:
        pr = repo.get_pull(prId)
        branch = pr.base.ref
        print("PR merged:", pr.merged)
        if pr.merged:
            return True
        from process_pr import get_changed_files

        chg_files = get_changed_files(repo, pr)
    USERS_TO_TRIGGER_HOOKS.add("cmsbuild")
    for comment in issue.get_comments():
        commenter = comment.user.login
        if not commenter in USERS_TO_TRIGGER_HOOKS:
            continue
        comment_msg = comment.body.encode("ascii", "ignore").decode()
        comment_lines = [l.strip() for l in comment_msg.split("\n") if l.strip()][0:1]
        print("Comment first line: %s => %s" % (commenter, comment_lines))
        if not comment_lines:
            continue
        first_line = comment_lines[0]
        if commenter == "cmsbuild":
            if not cmdType:
                continue
            if match("^Command\s+" + cmdType + "\s+acknowledged.$", first_line):
                print("Acknowledged ", cmdType)
                cmdType = None
            continue
        cmd = getCommentCommand(first_line)
        if not cmd:
            continue
        if (cmd == "ping") and cmdType:
            continue
        if (cmd == "test") and cmdType:
            continue
        if cmd == "merge" and not pr:
            continue
        if not hasRights(commenter, branch, cmd, chg_files):
            continue
        cmdType = cmd
        print("Found: Command %s issued by %s" % (cmdType, commenter))
    if not cmdType:
        return True
    print("Processing ", cmdType)
    if dryRun:
        return True
    if issue.state == "open":
        if cmdType == "merge":
            pr.merge()
        if cmdType == "close":
            issue.edit(state="closed")
        if cmdType == "test":
            mark_pr_ready_for_test(repo, pr)
    elif cmdType == "open":
        issue.edit(state="open")
    issue.create_comment("Command " + cmdType + " acknowledged.")
    return True


if __name__ == "__main__":
    parser = OptionParser(usage="%prog <pull-request-id>")
    parser.add_option(
        "-n",
        "--dry-run",
        dest="dryRun",
        action="store_true",
        help="Do not modify Github",
        default=False,
    )
    # parser.add_option("-r", "--repository", dest="repository", help="Github Repositoy name e.g. cms-sw/cmsdist.", type=str, default="cms-sw/cmsdist")
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Too many/few arguments")
    prId = int(args[0])

    repo_dir = join(SCRIPT_DIR, "repos", "cms-sw/cmsdist".replace("-", "_"))
    if exists(join(repo_dir, "repo_config.py")):
        sys.path.insert(0, repo_dir)
    import repo_config

    gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
    repo = gh.get_repo("cms-sw/cmsdist")
    if not process_pr(gh, repo, repo.get_issue(prId), opts.dryRun):
        exit(1)
    exit(0)
