#!/usr/bin/env python3
"""
Modifies last cmsbot message on Github
"""
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from optparse import OptionParser
import sys
from socket import setdefaulttimeout
import re

setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(sys.argv[0]))


def find_last_comment(issue, user, match):
    last_comment = None
    for comment in issue.get_comments():
        if (user != comment.user.login) or (not comment.body):
            continue
        if not re.match(
            match, comment.body.encode("ascii", "ignore").decode().strip("\n\t\r "), re.MULTILINE
        ):
            continue
        last_comment = comment
        print("Matched comment from %s with comment id %s" % (comment.user.login, comment.id))
    return last_comment


def modify_comment(comment, match, replace, dryRun):
    comment_msg = comment.body.encode("ascii", "ignore").decode() if comment.body else ""
    if match:
        new_comment_msg = re.sub(match, replace, comment_msg)
    else:
        new_comment_msg = comment_msg + "\n" + replace
    if new_comment_msg != comment_msg:
        if not dryRun:
            comment.edit(new_comment_msg)
            print("Message updated")
    return 0


valid_types = {}
valid_types["JENKINS_TEST_URL"] = ["", None]
valid_types["JENKINS_STYLE_URL"] = ["", None]
all_types = "|".join(valid_types)
if __name__ == "__main__":
    parser = OptionParser(
        usage="%prog [-n|--dry-run] [-r|--repository <repo>] -t|--type "
        + all_types
        + " -m|--message <message> <pull-request-id>"
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
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-t",
        "--type",
        dest="msgtype",
        help="Message type e.g. JENKINS_TEST_URL",
        type=str,
        default=None,
    )
    parser.add_option(
        "-m",
        "--message",
        dest="message",
        help="Message to be appened to the existing comment e.g. url of jenkins test job.",
        type=str,
        default=None,
    )

    opts, args = parser.parse_args()
    if len(args) != 1:
        parser.error("Too many/few arguments")
    if not opts.message:
        parser.error("Missing message to append")
    if not opts.msgtype:
        parser.error("Missing message type")
    if not opts.msgtype in valid_types:
        parser.error("Invalid message type " + opts.msgtype)

    repo_dir = join(SCRIPT_DIR, "repos", opts.repository.replace("-", "_"))
    if exists(join(repo_dir, "repo_config.py")):
        sys.path.insert(0, repo_dir)
    import repo_config
    from process_pr import TRIGERING_TESTS_MSG, TRIGERING_STYLE_TEST_MSG

    valid_types["JENKINS_TEST_URL"] = ["^\\s*" + TRIGERING_TESTS_MSG + ".*$", None]
    valid_types["JENKINS_STYLE_URL"] = ["^\\s*" + TRIGERING_STYLE_TEST_MSG + ".*$", None]
    gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
    issue = gh.get_repo(opts.repository).get_issue(int(args[0]))
    last_comment = find_last_comment(
        issue, repo_config.CMSBUILD_USER, valid_types[opts.msgtype][0]
    )
    if not last_comment:
        print("Warning: Not comment matched")
        sys.exit(1)
    print(last_comment.body)
    sys.exit(modify_comment(last_comment, valid_types[opts.msgtype][1], opts.message, opts.dryRun))
