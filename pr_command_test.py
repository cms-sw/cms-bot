import logging
import sys
import traceback
from optparse import OptionParser
from typing import Callable, Iterable, Union, Pattern, Optional
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
state = {}
ALL_CHECK_FUNCTIONS = {}
logger: Optional[logging.Logger] = None


### Helper functions ###


def ignore_issue(repo_config, repo, issue):
    if issue.number in repo_config.IGNORE_ISSUES:
        return True
    if (repo.full_name in repo_config.IGNORE_ISSUES) and (
            issue.number in repo_config.IGNORE_ISSUES[repo.full_name]
    ):
        return True
    if re.match(BUILD_REL, issue.title):
        return True
    if issue.body:
        if re.search(
                CMSBOT_IGNORE_MSG,
                issue.body.encode("ascii", "ignore").decode().split("\n", 1)[0].strip(),
                re.I,
        ):
            return True
    return False


def notify_user(issue):
    if issue.body and re.search(
            CMSBOT_NO_NOTIFY_MSG,
            issue.body.encode("ascii", "ignore").decode().split("\n", 1)[0].strip(),
            re.I,
    ):
        return False
    return True


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


def get_prs_list_from_string(pr_string="", repo_string=""):
    prs = []
    for pr in [
        x.strip().split("/github.com/", 1)[-1].replace("/pull/", "#").strip("/")
        for x in pr_string.split(",")
        if x.strip()
    ]:
        while "//" in pr:
            pr = pr.replace("//", "/")
        if pr.startswith("#"):
            pr = repo_string + pr
        prs.append(pr)
    return prs


# Read a yaml file
def read_repo_file(repo_config, repo_file, default=None, is_yaml=True):
    file_path = join(repo_config.CONFIG_DIR, repo_file)
    contents = default
    if exists(file_path):
        with open(file_path, "r") as f:
            if is_yaml:
                contents = yaml.load(f, Loader=Loader)
            else:
                contents = load(f)

        if not contents:
            contents = default
    return contents


def init_l2_data(repo_config, cms_repo):
    l2_data = {}
    if cms_repo:
        with open(join(dirname(__file__), "cmssw_l2", "l2.json")) as ref:
            default_l2_data = load(ref)
        l2_data = read_repo_file(repo_config, "l2.json", default_l2_data, False)
        for user in CMSSW_L2:
            if (user in l2_data) and ("end_date" in l2_data[user][-1]):
                del l2_data[user][-1]["end_date"]
    else:
        for user in CMSSW_L2:
            l2_data[user] = [{"start_date": 0, "category": CMSSW_L2[user]}]
    return l2_data


def update_CMSSW_LABELS(repo_config):
    check_dpg_pog = getattr(repo_config, "CHECK_DPG_POG", False)
    dpg_pog = {} if not check_dpg_pog else get_dpg_pog()
    for lab in CMSSW_LABELS.keys():
        if check_dpg_pog and (lab not in dpg_pog):
            del CMSSW_LABELS[lab]
        else:
            CMSSW_LABELS[lab] = [re.compile("^(" + p + ").*$") for p in CMSSW_LABELS[lab]]
    return


def updateMilestone(repo, issue, pr, dryRun):
    milestoneId = RELEASE_BRANCH_MILESTONE.get(pr.base.label.split(":")[1], None)
    if not milestoneId:
        print("Unable to find a milestone for the given branch")
        return
    if pr.state != "open":
        print("PR not open, not setting/checking milestone")
        return
    if issue.milestone and issue.milestone.number == milestoneId:
        return
    milestone = repo.get_milestone(milestoneId)
    print("Setting milestone to %s" % milestone.title)
    if dryRun:
        return
    issue.edit(milestone=milestone)


def get_changed_files(repo, pr, use_gh_patch=False):
    if (not use_gh_patch) and (pr.changed_files <= 300):
        pr_files = []
        for f in pr.get_files():
            pr_files.append(f.filename)
            try:
                if f.previous_filename:
                    pr_files.append(f.previous_filename)
            except:
                pass
        print("PR Files: ", pr_files)
        return pr_files
    cmd = (
            "curl -s -L https://patch-diff.githubusercontent.com/raw/%s/pull/%s.patch | grep '^diff --git ' | sed 's|.* a/||;s|  *b/| |' | tr ' ' '\n' | sort | uniq"
            % (repo.full_name, pr.number)
    )
    e, o = run_cmd(cmd)
    if e:
        return []
    return o.split("\n")


def get_backported_pr(msg):
    if BACKPORT_STR in msg:
        bp_num = msg.split(BACKPORT_STR, 1)[-1].split("\n", 1)[0].strip()
        if re.match("^[1-9][0-9]*$", bp_num):
            return bp_num
    return ""


def cmssw_file2Package(repo_config, filename):
    try:
        return repo_config.file2Package(filename)
    except:
        return "/".join(filename.split("/", 2)[0:2])


def get_jenkins_job(issue):
    test_line = ""
    for line in [l.strip() for l in issue.body.encode("ascii", "ignore").decode().split("\n")]:
        if line.startswith("Build logs are available at:"):
            test_line = line
    if test_line:
        test_line = test_line.split("Build logs are available at: ", 1)[-1].split("/")
        if test_line[-4] == "job" and test_line[-1] == "console":
            return test_line[-3], test_line[-2]
    return "", ""


def get_status(context, statuses):
    for s in statuses:
        if s.context == context:
            return s
    return None


def get_status_state(context, statuses):
    s = get_status(context, statuses)
    if s:
        return s.state
    return ""


def dumps_maybe_compress(value):
    json_ = dumps(value, separators=(",", ":"), sort_keys=True)
    if len(json_) > 32000:
        return "b64:" + base64.encodebytes(zlib.compress(json_.encode())).decode("ascii", "ignore")
    else:
        return json_


def loads_maybe_decompress(data):
    if data.startswith("b64:"):
        data = zlib.decompress(base64.decodebytes(data[4:].encode())).decode()

    return loads(data)


def add_nonblocking_labels(chg_files, extra_labels):
    for pkg_file in chg_files:
        for ex_lab, pkgs_regexp in list(CMSSW_LABELS.items()):
            for regex in pkgs_regexp:
                if regex.match(pkg_file):
                    extra_labels["mtype"].append(ex_lab)
                    print("Non-Blocking label:%s:%s:%s" % (ex_lab, regex.pattern, pkg_file))
                    break
    if ("mtype" in extra_labels) and (not extra_labels["mtype"]):
        del extra_labels["mtype"]
    print("Extra non-blocking labels:", extra_labels)
    return

def get_package_categories(package):
    cats = []
    for cat, packages in list(CMSSW_CATEGORIES.items()):
        if package in packages:
            cats.append(cat)
    return cats

### Functions to check for test parameters' correctness ###

def check_function(func):
    def wrapper(*args, **kwargs):
        fname = re.sub("^check_", "", func.__name__.lower())
        ALL_CHECK_FUNCTIONS[fname] = func
        return func(*args, **kwargs)

    return wrapper


checks = {}


@check_function
def check_extra_labels(first_line, extra_labels):
    if "urgent" in first_line:
        extra_labels["urgent"] = ["urgent"]
    elif "backport" in first_line:
        if "#" in first_line:
            bp_pr = first_line.split("#", 1)[1].strip()
        else:
            bp_pr = first_line.split("/pull/", 1)[1].strip("/").strip()
        extra_labels["backport"] = ["backport", bp_pr]


@check_function
def check_type_labels(first_line, extra_labels, state_labels):
    ex_labels = {}
    rem_labels = {}
    for type_cmd in [x.strip() for x in first_line.split(" ", 1)[-1].split(",") if x.strip()]:
        valid_lab = False
        rem_lab = type_cmd[0] == "-"
        if type_cmd[0] in ["-", "+"]:
            type_cmd = type_cmd[1:]
        for lab in TYPE_COMMANDS:
            if re.match("^%s$" % TYPE_COMMANDS[lab][1], type_cmd, re.I):
                lab_type = TYPE_COMMANDS[lab][2]
                obj_labels = rem_labels if rem_lab else ex_labels
                if lab_type not in obj_labels:
                    obj_labels[lab_type] = []
                if (len(TYPE_COMMANDS[lab]) > 4) and TYPE_COMMANDS[lab][4] == "state":
                    state_labels[lab] = type_cmd
                elif (len(TYPE_COMMANDS[lab]) > 3) and TYPE_COMMANDS[lab][3]:
                    obj_labels[lab_type].append(type_cmd)
                else:
                    obj_labels[lab_type].append(lab)
                valid_lab = True
                break
        if not valid_lab:
            return valid_lab
    for ltype in ex_labels:
        if ltype not in extra_labels:
            extra_labels[ltype] = []
        for lab in ex_labels[ltype]:
            extra_labels[ltype].append(lab)
    for ltype in rem_labels:
        if ltype not in extra_labels:
            continue
        for lab in rem_labels[ltype]:
            if lab not in extra_labels[ltype]:
                continue
            while lab in extra_labels[ltype]:
                extra_labels[ltype].remove(lab)
            if not extra_labels[ltype]:
                del extra_labels[ltype]
                break
    return True


@check_function
def check_ignore_bot_tests(first_line, *args):
    return first_line.upper().replace(" ", ""), None


@check_function
def check_enable_bot_tests(first_line, *args):
    tests = first_line.upper().replace(" ", "")
    if "NONE" in tests:
        tests = "NONE"
    return tests, None


@check_function
def check_extra_matrix_args(first_line, repo, params, mkey, param, *args):
    kitem = mkey.split("_")
    print(first_line, repo, params, mkey, param)
    if kitem[-1] in ["input"] + EXTRA_RELVALS_TESTS:
        param = param + "_" + kitem[-1].upper().replace("-", "_")
    print(first_line, param)
    return first_line, param


@check_function
def check_matrix_extras(first_line, repo, params, mkey, param, *args):
    kitem = mkey.split("_")
    print(first_line, repo, params, mkey, param)
    if kitem[-1] in EXTRA_RELVALS_TESTS:
        param = param + "_" + kitem[-1].upper().replace("-", "_")
    print(first_line, param)
    return first_line, param


@check_function
def check_pull_requests(first_line, repo, *args):
    return " ".join(get_prs_list_from_string(first_line, repo)), None


@check_function
def check_release_format(first_line, repo, params, *args):
    rq = first_line
    ra = ""
    if "/" in rq:
        rq, ra = rq.split("/", 1)
    elif re.match("^" + ARCH_PATTERN + "$", rq):
        ra = rq
        rq = ""
    params["ARCHITECTURE_FILTER"] = ra
    return rq, None


@check_function
def check_test_cmd(first_line, repo, params):
    m = REGEX_TEST_REG.match(first_line)
    if m:
        wfs = ""
        prs = []
        cmssw_que = ""
        print(m.groups())
        if m.group(6):
            wfs = ",".join(set(m.group(6).replace(" ", "").split(",")))
        if m.group(11):
            prs = get_prs_list_from_string(m.group(11), repo)
        if m.group(20):
            cmssw_que = m.group(20)
        if m.group(23):
            if "addpkg" in m.group(23):
                params["EXTRA_CMSSW_PACKAGES"] = m.group(25).strip()
            else:
                params["BUILD_FULL_CMSSW"] = "true"
        return True, " ".join(prs), wfs, cmssw_que
    return False, "", "", ""


### Commands ###

commands = {}


def command(
        *,
        trigger: Union[str, Pattern, Callable],
        acl: Union[str, Iterable[str], Callable, None] = None,
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
def ping(pr, comment, comment_lines, repo):
    return True


@command(trigger=TEST_REGEXP, acl=["iarspider"])
def test(pr, comment, comment_lines, repo):
    # pr.create_comment("Test started")
    return True


@command(trigger=re.compile("test parameters:?", re.I))
def test_params(pr, comment, comment_lines, repo):
    global ALL_CHECK_FUNCTIONS
    xerrors = {"format": [], "key": [], "value": []}
    matched_extra_args = {}
    for line_ in comment_lines[1:]:
        line_ = line_.strip().lstrip(" \t*-")
        if line_ == "":
            continue
        if "=" not in line_:
            xerrors["format"].append("'%s'" % line_)
            continue
        line_args = line_.split("=", 1)
        line_args[0] = line_args[0].replace(" ", "").lower()
        line_args[1] = line_args[1].strip()
        found = False
        for k, pttrn in MULTILINE_COMMENTS_MAP.items():
            if not re.match("^(%s)$" % k, line_args[0], re.I):
                continue
            if (len(pttrn) < 3) or (not pttrn[2]):
                line_args[1] = line_args[1].replace(" ", "").lower()
            param = pttrn[1]
            if not re.match("^(%s)$" % pttrn[0], line_args[1], re.I):
                xerrors["value"].append(line_args[0])
                found = True
                break
            func = "check_%s" % param.lower()
            # noinspection PyBroadException
            try:
                if func in ALL_CHECK_FUNCTIONS:
                    line_args[1], new_param = ALL_CHECK_FUNCTIONS[func](
                        line_args[1], repo, matched_extra_args, line_args[0], param
                    )
                    if new_param:
                        param = new_param
            except Exception:
                logger.exception("Check function %s raised an exception", func)
                pass
            matched_extra_args[param] = line_args[1]
            found = True
            break
        if not found:
            xerrors["key"].append(line_args[0])
    error_lines = []
    for k in sorted(xerrors.keys()):
        if xerrors[k]:
            error_lines.append("%s:%s" % (k, ",".join(xerrors[k])))
    if error_lines:
        matched_extra_args = {"errors": "ERRORS: " + "; ".join(error_lines)}
    state["matched_extra_args"] = matched_extra_args


def check_acl(comment: IssueComment, command_acl: Union[str, Iterable[str], Callable]) -> bool:
    if command_acl is None:
        return True
    elif isinstance(command_acl, str):
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
        res = cmd["code"](pr, comment, comment_lines, repo)
        if cmd["ack"]:
            print("Command", "succeeded" if res else "failed")
            set_comment_emoji_cache(True, comment, repo, "+1" if res else "-1")

        break


### Main function ###


def process_pr(repo_config, gh, repo, issue, dryRun, cmsbuild_user=None, force=False, loglevel=logging.DEBUG):
    global L2_DATA, logger
    if (not force) and ignore_issue(repo_config, repo, issue):
        return

    logger = logging.getLogger("process_pr")
    logger.setLevel(loglevel)

    gh_user_char = "@"
    if not notify_user(issue):
        gh_user_char = ""
    api_rate_limits(gh)
    prId = issue.number
    repository = repo.full_name
    repo_org, repo_name = repository.split("/", 1)
    auto_test_repo = AUTO_TEST_REPOS
    if getattr(repo_config, "AUTO_TEST_REPOS", False):
        auto_test_repo = [repository]

    if not cmsbuild_user:
        cmsbuild_user = repo_config.CMSBUILD_USER
    logger.info("Working on %s for PR/Issue %s with admin user %s", repo.full_name, prId, cmsbuild_user)
    logger.debug("Notify User: %s", gh_user_char)

    update_CMSSW_LABELS(repo_config)
    set_gh_user(cmsbuild_user)
    cmssw_repo = repo_name == GH_CMSSW_REPO
    cms_repo = repo_org in EXTERNAL_REPOS
    external_repo = (repository != CMSSW_REPO_NAME) and (
            len([e for e in EXTERNAL_REPOS if repo_org == e]) > 0
    )
    # create_test_property = False
    # packages = set([])
    # chg_files = []
    package_categories = {}
    extra_labels = {"mtype": []}
    # state_labels = {}
    # add_external_category = False
    signing_categories = set([])
    # new_package_message = ""
    # mustClose = False
    # reOpen = False
    # releaseManagers = []
    # watchers = []
    # # Process Pull Request
    pkg_categories = set([])
    REGEX_TYPE_CMDS = (
        r"^(type|(build-|)state)\s+(([-+]|)[a-z][a-z0-9_-]+)(\s*,\s*([-+]|)[a-z][a-z0-9_-]+)*$"
    )
    REGEX_EX_CMDS = r"^urgent$|^backport\s+(of\s+|)(#|http(s|):/+github\.com/+%s/+pull/+)\d+$" % (
        repo.full_name
    )  # TODO: \s*
    known_ignore_tests = "%s" % MULTILINE_COMMENTS_MAP["ignore_test(s|)"][0]
    REGEX_EX_IGNORE_CHKS = r"^ignore\s+((%s)(\s*,\s*(%s))*|none)$" % (
        known_ignore_tests,
        known_ignore_tests,
    )  # TODO: \s*
    REGEX_EX_ENABLE_TESTS = r"^enable\s+(%s)$" % MULTILINE_COMMENTS_MAP[ENABLE_TEST_PTRN][0]  # TODO: \s*
    L2_DATA = init_l2_data(repo_config, cms_repo)
    # last_commit_date = None
    # last_commit_obj = None
    # push_test_issue = False
    requestor = issue.user.login.encode("ascii", "ignore").decode()
    # ignore_tests = ""
    # enable_tests = ""
    # commit_statuses = None
    # bot_status_name = "bot/jenkins"
    # bot_ack_name = "bot/ack"
    # bot_test_param_name = "bot/test_parameters"
    # cms_status_prefix = "cms"
    # bot_status = None
    # code_checks_status = []
    # pre_checks_state = {}
    # default_pre_checks = ["code-checks"]
    # # For future pre_checks
    # # if prId>=somePRNumber: default_pre_checks+=["some","new","checks"]
    # pre_checks_url = {}
    # events = defaultdict(list)
    # all_commits = []
    # all_commit_shas = set()
    # ok_too_many_commits = False
    # warned_too_many_commits = False

    if issue.pull_request:
        pr = repo.get_pull(prId)
        if pr.changed_files == 0:
            logger.warning("Ignoring: PR with no files changed")
            return
        if cmssw_repo and cms_repo and (pr.base.ref == CMSSW_DEVEL_BRANCH):
            if pr.state != "closed":
                print("This pull request must go in to master branch")
                if not dryRun:
                    edit_pr(repo.full_name, prId, base="master")
                    msg = (
                        "{gh_user_char}{user}, {dev_branch} branch is closed for direct updates. cms-bot is going to move this PR to master branch.\n"
                        "In future, please use cmssw master branch to submit your changes.\n".format(
                            user=requestor,
                            gh_user_char=gh_user_char,
                            dev_branch=CMSSW_DEVEL_BRANCH,
                        ))
                    issue.create_comment(msg)
            return

        # A pull request is by default closed if the branch is a closed one.
        if is_closed_branch(pr.base.ref):
            mustClose = True

        # Process the changes for the given pull request so that we can determine the
        # signatures it requires.
        if cmssw_repo or not external_repo:
            if cmssw_repo:
                if pr.base.ref == "master":
                    signing_categories.add("code-checks")
                updateMilestone(repo, issue, pr, dryRun)
            chg_files = get_changed_files(repo, pr)
            packages = sorted(
                [x for x in set([cmssw_file2Package(repo_config, f) for f in chg_files])]
            )
            add_nonblocking_labels(chg_files, extra_labels)
            create_test_property = True
        else:
            add_external_category = True
            packages = {"externals/" + repository}
            ex_pkg = external_to_package(repository)
            if ex_pkg:
                packages.add(ex_pkg)
            if (repo_org != GH_CMSSW_ORGANIZATION) or (repo_name in VALID_CMS_SW_REPOS_FOR_TESTS):
                create_test_property = True
            if (repo_name == GH_CMSDIST_REPO) and (
                    not re.match(VALID_CMSDIST_BRANCHES, pr.base.ref)
            ):
                print("Skipping PR as it does not belong to valid CMSDIST branch")
                return

            if hasattr(repo_config, "NONBLOCKING_LABELS"):
                chg_files = get_changed_files(repo, pr)
                add_nonblocking_labels(chg_files, extra_labels)

        print("Following packages affected:")
        print("\n".join(packages))
        for package in packages:
            package_categories[package] = set([])
            for category in get_package_categories(package):
                package_categories[package].add(category)
                pkg_categories.add(category)
        signing_categories.update(pkg_categories)

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
