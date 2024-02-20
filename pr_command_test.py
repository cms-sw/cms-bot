import sys
from optparse import OptionParser
from typing import Callable, Iterable, Union, Pattern
from github.IssueComment import IssueComment
from github.Issue import Issue
from github.PullRequest import PullRequest
import base64
import functools
import re
import zlib
from collections import defaultdict
from datetime import datetime
from json import dumps, load, loads
from os.path import join, exists, dirname, abspath
from socket import setdefaulttimeout

import yaml
from github.Repository import Repository

from _py2with3compatibility import run_cmd
from categories import CMSSW_CATEGORIES
from categories import (
    CMSSW_L2,
    CMSSW_L1,
    TRIGGER_PR_TESTS,
    CMSSW_ISSUES_TRACKERS,
    PR_HOLD_MANAGERS,
    EXTERNAL_REPOS,
)
from cms_static import BACKPORT_STR, GH_CMSSW_ORGANIZATION, CMSBOT_NO_NOTIFY_MSG
from cms_static import (
    VALID_CMSDIST_BRANCHES,
    NEW_ISSUE_PREFIX,
    NEW_PR_PREFIX,
    ISSUE_SEEN_MSG,
    BUILD_REL,
    GH_CMSSW_REPO,
    GH_CMSDIST_REPO,
    CMSBOT_IGNORE_MSG,
    VALID_CMS_SW_REPOS_FOR_TESTS,
    CREATE_REPO,
    CMSBOT_TECHNICAL_MSG,
)
from github_utils import (
    edit_pr,
    api_rate_limits,
    get_pr_commits_reversed,
    get_commit,
    get_gh_token,
)
from github_utils import set_comment_emoji, get_comment_emojis, set_gh_user
from github_utils import set_issue_emoji, get_issue_emojis
from githublabels import TYPE_COMMANDS, TEST_IGNORE_REASON
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, CMSSW_DEVEL_BRANCH
from repo_config import GH_REPO_ORGANIZATION

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


try:
    from categories import CMSSW_LABELS
except ImportError:
    CMSSW_LABELS = {}
try:
    from categories import get_dpg_pog
except ImportError:

    def get_dpg_pog(*args):
        return {}


try:
    from categories import external_to_package
except ImportError:

    def external_to_package(*args):
        return ""


try:
    from releases import get_release_managers, is_closed_branch
except ImportError:

    def get_release_managers(*args):
        return []

    def is_closed_branch(*args):
        return False


setdefaulttimeout(300)
CMSDIST_REPO_NAME = join(GH_REPO_ORGANIZATION, GH_CMSDIST_REPO)
CMSSW_REPO_NAME = join(GH_REPO_ORGANIZATION, GH_CMSSW_REPO)


# Prepare various comments regardless of whether they will be made or not.
BOT_CACHE_TEMPLATE = {"emoji": {}, "signatures": {}, "commits": {}}
TRIGERING_TESTS_MSG = "The tests are being triggered in jenkins."
TRIGERING_TESTS_MSG1 = "Jenkins tests started for "
TRIGERING_STYLE_TEST_MSG = "The project style tests are being triggered in jenkins."
IGNORING_TESTS_MSG = "Ignoring test request."
TESTS_RESULTS_MSG = r"^\s*([-|+]1|I had the issue.*)\s*$"
FAILED_TESTS_MSG = "The jenkins tests job failed, please try again."
PUSH_TEST_ISSUE_MSG = r"^\[Jenkins CI\] Testing commit: [0-9a-f]+$"
HOLD_MSG = "Pull request has been put on hold by "
# Regexp to match the test requests
CODE_CHECKS_REGEXP = re.compile(
    r"code-checks(\s+with\s+cms.week[0-9].PR_[0-9a-f]{8}/\S+|)(\s+and\s+apply\s+patch|)$"
)
WF_PATTERN = r"[1-9][0-9]*(\.[0-9]+|)"
CMSSW_QUEUE_PATTERN = "CMSSW_[0-9]+_[0-9]+_(X|[A-Z][A-Z0-9]+_X|[0-9]+(_[a-zA-Z0-9_]+|))"
CMSSW_PACKAGE_PATTERN = "[A-Z][a-zA-Z0-9]+(/[a-zA-Z0-9]+|)"
ARCH_PATTERN = "[a-z0-9]+_[a-z0-9]+_[a-z0-9]+"
CMSSW_RELEASE_QUEUE_PATTERN = "({cmssw}|{arch}|{cmssw}/{arch})".format(
    cmssw=CMSSW_QUEUE_PATTERN, arch=ARCH_PATTERN
)

RELVAL_OPTS = r"[-][a-zA-Z0-9_.,\s/'-]+"
CLOSE_REQUEST = re.compile(r"^\s*((@|)cmsbuild\s*,*\s+|)(please\s*,*\s+|)close\s*$", re.I)
REOPEN_REQUEST = re.compile(r"^\s*((@|)cmsbuild\s*,*\s+|)(please\s*,*\s+|)(re|)open\s*$", re.I)
CMS_PR_PATTERN = (
    "(#[1-9][0-9]*|({cmsorgs})/+[a-zA-Z0-9_-]+#[1-9][0-9]*|https://+github.com/+({cmsorgs})/+[a-zA-Z0-9_-]+/+pull/+[1-9][0-9]*)".format(
        cmsorgs="|".join(EXTERNAL_REPOS)
    ),
)

TEST_REGEXP = r"^\s*((@|)cmsbuild\s*,*\s+|)(please\s*,*\s+|)test(\s+workflow(s|)\s+({workflow}(\s*,\s*{workflow}|)*)|)(\s+with\s+({cms_pr}(\s*,\s*{cms_pr})*)|)(\s+for\s+{release_queue}|)(\s+using\s+full\s+cmssw|\s+using\s+(cms-|)addpkg\s+({pkg}(,{pkg})*)|)\s*$".format(
    workflow=WF_PATTERN,
    cms_pr=CMS_PR_PATTERN,
    pkg=CMSSW_PACKAGE_PATTERN,
    release_queue=CMSSW_RELEASE_QUEUE_PATTERN,
)

AUTO_TEST_REPOS = ["cms-sw/cmssw"]
REGEX_TEST_REG = re.compile(TEST_REGEXP, re.I)
REGEX_TEST_ABORT = re.compile(
    r"^\s*((@|)cmsbuild\s*,*\s+|)(please\s*,*\s+|)abort(\s+test|)$", re.I
)
REGEX_TEST_IGNORE = re.compile(
    r"^\s*(?:(?:@|)cmsbuild\s*,*\s+|)(?:please\s*,*\s+|)ignore\s+tests-rejected\s+(?:with|)([a-z -]+)$",
    re.I,
)
REGEX_COMMITS_CACHE = re.compile(r"<!-- (?:commits|bot) cache: (.*) -->")
REGEX_IGNORE_COMMIT_COUNT = r"\+commit-count"
TEST_WAIT_GAP = 720
ALL_CHECK_FUNCTIONS = None
EXTRA_RELVALS_TESTS = ["threading", "gpu", "high-stats", "nano"]
EXTRA_RELVALS_TESTS_OPTS = "_" + "|_".join(EXTRA_RELVALS_TESTS)
EXTRA_TESTS = "|".join(EXTRA_RELVALS_TESTS) + "|profiling|none"
SKIP_TESTS = "|".join(["static", "header"])
ENABLE_TEST_PTRN = "enable(_test(s|)|)"
JENKINS_NODES = r"[a-zA-Z0-9_|&\s()-]+"
MULTILINE_COMMENTS_MAP = {
    "(workflow|relval)(s|)("
    + EXTRA_RELVALS_TESTS_OPTS
    + "|)": [r"{workflow}(\s*,\s*{workflow}|)*".format(workflow=WF_PATTERN), "MATRIX_EXTRAS"],
    "(workflow|relval)(s|)_profiling": [
        r"{workflow}(\s*,\s*{workflow}|)*".format(workflow=WF_PATTERN),
        "PROFILING_WORKFLOWS",
    ],
    "pull_request(s|)": [
        "{cms_pr}(,{cms_pr})*".format(cms_pr=CMS_PR_PATTERN),
        "PULL_REQUESTS",
    ],
    "full_cmssw|full": ["true|false", "BUILD_FULL_CMSSW"],
    "disable_poison": ["true|false", "DISABLE_POISON"],
    "use_ib_tag": ["true|false", "USE_IB_TAG"],
    "baseline": ["self|default", "USE_BASELINE"],
    "skip_test(s|)": [r"({tests})(\s*,\s*({tests}))*".format(tests=SKIP_TESTS), "SKIP_TESTS"],
    "dry_run": ["true|false", "DRY_RUN"],
    "jenkins_(slave|node)": [JENKINS_NODES, "RUN_ON_SLAVE"],
    "(arch(itecture(s|))|release|release/arch)": [
        CMSSW_RELEASE_QUEUE_PATTERN,
        "RELEASE_FORMAT_FORMAT",
    ],
    ENABLE_TEST_PTRN: [
        r"({tests})(\s*,\s*({tests}))*".format(tests=EXTRA_TESTS),
        "ENABLE_BOT_TESTS",
    ],
    "ignore_test(s|)": ["build-warnings|clang-warnings", "IGNORE_BOT_TESTS"],
    "container": [
        "[a-zA-Z][a-zA-Z0-9_-]+/[a-zA-Z][a-zA-Z0-9_-]+(:[a-zA-Z0-9_-]+|)",
        "DOCKER_IMGAGE",
    ],
    "cms-addpkg|addpkg": [
        "{pkg}(,{pkg})*".format(pkg=CMSSW_PACKAGE_PATTERN),
        "EXTRA_CMSSW_PACKAGES",
    ],
    "build_verbose": ["true|false", "BUILD_VERBOSE"],
    "(workflow|relval)(s|)_opt(ion|)(s|)("
    + EXTRA_RELVALS_TESTS_OPTS
    + "|_input|)": [RELVAL_OPTS, "EXTRA_MATRIX_ARGS", True],
    "(workflow|relval)(s|)_command_opt(ion|)(s|)("
    + EXTRA_RELVALS_TESTS_OPTS
    + "|_input|)": [RELVAL_OPTS, "EXTRA_MATRIX_COMMAND_ARGS", True],
}

REGEX_PLEASE = re.compile(r"\s*(?:(?:@|)cmsbuild\s*,*\s+|)(?:please\s*,*\s+|)", re.I)

TOO_MANY_COMMITS_WARN_THRESHOLD = 150
TOO_MANY_COMMITS_FAIL_THRESHOLD = 240
L2_DATA = {}

bot_cache = {}


def set_comment_emoji_cache(dryRun, comment, repository, emoji="+1", reset_other=True):
    global bot_cache

    if dryRun:
        return
    comment_id = str(comment.id)
    if (
        (comment_id not in bot_cache["emoji"])
        or (bot_cache["emoji"][comment_id] != emoji)
        or (comment.reactions[emoji] == 0)
    ):
        if "Issue.Issue" in str(type(comment)):
            set_issue_emoji(comment.number, repository, emoji=emoji, reset_other=reset_other)
        else:
            set_comment_emoji(comment.id, repository, emoji=emoji, reset_other=reset_other)
        bot_cache["emoji"][comment_id] = emoji
    return


commands = {}


def command(
    *,
    trigger: Union[str, Pattern, Callable],
    acl: Union[str, Iterable[str], Callable],
    ack: bool = True,
    multiline: bool = False,
):
    def decorator(func):
        commands[func.__name__] = {
            "code": func,
            "trigger": trigger,
            "acl": acl,
            "ack": ack,
            "multiline": multiline,
        }

    return decorator


@command(trigger="ping", acl=["iarspider"])
def ping(pr, comment, comment_lines):
    return True


@command(trigger=TEST_REGEXP, acl=["iarspider"])
def test(pr, comment, comment_lines):
    # pr.create_comment("Test started")
    return True


def check_acl(comment: IssueComment, command_acl: Union[str, Iterable[str], Callable]) -> bool:
    if isinstance(command_acl, str):
        return comment.user.login == command_acl
    elif isinstance(command_acl, Iterable):
        return comment.user.login in command_acl
    elif callable(command_acl):
        return command_acl(comment.user.login)
    else:
        raise TypeError()


def check_trigger(
    first_line: str,
    comment_lines: Iterable[str],
    multiline: bool,
    command_trigger: Union[str, Pattern, Callable],
) -> bool:
    first_line = comment_lines[0:1]

    if callable(command_trigger):
        return command_trigger("\n".join(comment_lines) if multiline else first_line)
    elif isinstance(command_trigger, Pattern):
        return (
            command_trigger.match(
                "\n".join(comment_lines) if multiline else first_line,
            )
            is not None
        )
    elif isinstance(command_trigger, str):
        return (
            re.match(
                "^" + command_trigger + "$",
                "\n".join(comment_lines),
                re.MULTILINE if multiline else 0,
            )
            is not None
        )
    else:
        raise TypeError()


def process_comment(pr: Union[PullRequest, Issue], comment: IssueComment, repo: Repository):
    comment_msg = comment.body.encode("ascii", "ignore").decode() if comment.body else ""
    comment_lines = list(
        comment_line.strip() for comment_line in comment_msg.split("\n") if comment_line.strip()
    )
    first_line = REGEX_PLEASE.sub("".join(comment_lines[0:1]), "")

    for k, cmd in commands.items():
        print("Checking command", k)

        try:
            res = check_trigger(first_line, comment_lines, cmd["multiline"], cmd["trigger"])
        except TypeError:
            raise RuntimeError(
                "Error processing command {0}: invalid trigger type {1}".format(k, cmd["trigger"])
            )

        if not res:
            print("-- Trigger not matched")
            continue
        else:
            print("-- Trigger matched")

        try:
            res = check_acl(comment, cmd["acl"])
        except TypeError:
            raise RuntimeError(
                "Error processing command {0}: invalid ACL type {1}".format(k, cmd["acl"])
            )

        if not res:
            print(
                "ERROR: user {0} is not authorised to use command {1}".format(
                    comment.user.login, k
                )
            )
            break
        else:
            print("-- ACL check passed")

        print("Executing command", k)
        res = cmd["code"](pr, comment, comment_lines)
        if cmd["ack"]:
            print("Command", "succeeded" if res else "failed")
            set_comment_emoji_cache(True, comment, repo, "+1" if res else "-1")

        break


def process_pr(repo_config, gh, repo, issue, dryRun, cmsbuild_user=None, force=False):
    for comment in issue.get_comments():
        # all_comments.append(comment)
        process_comment(issue, comment, repo)
    pass


def main():
    SCRIPT_DIR = dirname(abspath(sys.argv[0]))
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
    if len(args) != 1:
        parser.error("Too many/few arguments")
    prId = int(args[0])  # Positional argument is "Pull request ID"

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
    process_pr(repo_config, gh, repo, repo.get_issue(prId), opts.dryRun, force=opts.force)
    api_rate_limits(gh)


if __name__ == "__main__":
    main()
