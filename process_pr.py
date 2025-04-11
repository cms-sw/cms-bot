import copy

from categories import (
    CMSSW_L2,
    CMSSW_ORP,
    TRIGGER_PR_TESTS,
    CMSSW_ISSUES_TRACKERS,
    PR_HOLD_MANAGERS,
    EXTERNAL_REPOS,
    CMSDIST_REPOS,
)
from categories import CMSSW_CATEGORIES
from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, CMSSW_DEVEL_BRANCH
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
from cms_static import BACKPORT_STR, GH_CMSSW_ORGANIZATION, CMSBOT_NO_NOTIFY_MSG
from githublabels import TYPE_COMMANDS, TEST_IGNORE_REASON
from repo_config import GH_REPO_ORGANIZATION
import re, time
from collections import defaultdict
import zlib, base64
from datetime import datetime
from os.path import join, exists, dirname
from os import environ
from github_utils import (
    edit_pr,
    api_rate_limits,
    get_pr_commits_reversed,
    get_commit,
)
from github_utils import set_gh_user, get_gh_user
from socket import setdefaulttimeout
from _py2with3compatibility import run_cmd
from json import dumps, dump, load, loads
import yaml
import logging
import sys

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper
try:
    from categories import CATS_TO_APPROVE_ON_TEST
except:
    CATS_TO_APPROVE_ON_TEST = []
try:
    from categories import CMSSW_LABELS
except:
    CMSSW_LABELS = {}
try:
    from categories import get_dpg_pog
except:

    def get_dpg_pog(*args):
        return {}


try:
    from categories import external_to_package
except:

    def external_to_package(*args):
        return ""


try:
    from releases import get_release_managers, is_closed_branch
except:

    def get_release_managers(*args):
        return []

    def is_closed_branch(*args):
        return False


setdefaulttimeout(300)
CMSDIST_REPO_NAME = join(GH_REPO_ORGANIZATION, GH_CMSDIST_REPO)
CMSSW_REPO_NAME = join(GH_REPO_ORGANIZATION, GH_CMSSW_REPO)


# Prepare various comments regardless of whether they will be made or not.
def format(s, **kwds):
    return s % kwds


BOT_CACHE_TEMPLATE = {"emoji": {}, "signatures": {}, "commits": {}}
TRIGERING_TESTS_MSG = "The tests are being triggered in jenkins."
TRIGERING_TESTS_MSG1 = "Jenkins tests started for "
TRIGERING_STYLE_TEST_MSG = "The project style tests are being triggered in jenkins."
IGNORING_TESTS_MSG = "Ignoring test request."
TESTS_RESULTS_MSG = "^\\s*([-|+]1|I had the issue.*)\\s*$"
FAILED_TESTS_MSG = "The jenkins tests job failed, please try again."
PUSH_TEST_ISSUE_MSG = "^\\[Jenkins CI\\] Testing commit: [0-9a-f]+$"
HOLD_MSG = "Pull request has been put on hold by "
# Regexp to match the test requests
CODE_CHECKS_REGEXP = re.compile(
    r"code-checks(\s+with\s+cms.week[0-9].PR_[0-9a-f]{8}/[^\s]+|)(\s+and\s+apply\s+patch|)$"
)
WF_PATTERN = r"[1-9][0-9]*(\.[0-9]+|)"
CMSSW_QUEUE_PATTERN = "CMSSW_[0-9]+_[0-9]+_(X|[A-Z][A-Z0-9]+_X|[0-9]+(_[a-zA-Z0-9_]+|))"
CMSSW_PACKAGE_PATTERN = "[A-Z][a-zA-Z0-9]+(/[a-zA-Z0-9]+|)"
ARCH_PATTERN = "[a-z0-9]+_[a-z0-9]+_[a-z0-9]+"
CMSSW_RELEASE_QUEUE_PATTERN = format(
    "(%(cmssw)s|%(arch)s|%(cmssw)s/%(arch)s)", cmssw=CMSSW_QUEUE_PATTERN, arch=ARCH_PATTERN
)
RELVAL_OPTS = r"[-][a-zA-Z0-9_.,\s/'-]+"
CLOSE_REQUEST = re.compile(r"^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)close\s*$", re.I)
REOPEN_REQUEST = re.compile(r"^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)(re|)open\s*$", re.I)
CMS_PR_PATTERN = format(
    "(#[1-9][0-9]*|(%(cmsorgs)s)/+[a-zA-Z0-9_-]+#[1-9][0-9]*|https://+github.com/+(%(cmsorgs)s)/+[a-zA-Z0-9_-]+/+pull/+[1-9][0-9]*)",
    cmsorgs="|".join(EXTERNAL_REPOS),
)
TEST_REGEXP = format(
    r"^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)test(\s+workflow(s|)\s+(%(workflow)s(\s*,\s*%(workflow)s|)*)|)(\s+with\s+(%(cms_pr)s(\s*,\s*%(cms_pr)s)*)|)(\s+for\s+%(release_queue)s|)(\s+using\s+full\s+cmssw|\s+using\s+(cms-|)addpkg\s+(%(pkg)s(,%(pkg)s)*)|)\s*$",
    workflow=WF_PATTERN,
    cms_pr=CMS_PR_PATTERN,
    pkg=CMSSW_PACKAGE_PATTERN,
    release_queue=CMSSW_RELEASE_QUEUE_PATTERN,
)

AUTO_TEST_REPOS = ["cms-sw/cmssw"]
REGEX_TEST_REG = re.compile(TEST_REGEXP, re.I)
REGEX_TEST_ABORT = re.compile(
    r"^\s*((@|)cmsbuild\s*[,]*\s+|)(please\s*[,]*\s+|)abort(\s+test|)$", re.I
)
REGEX_TEST_IGNORE = re.compile(
    r"^\s*(?:(?:@|)cmsbuild\s*[,]*\s+|)(?:please\s*[,]*\s+|)ignore\s+tests-rejected\s+(?:with|)([a-z -]+)$",
    re.I,
)
REGEX_COMMITS_CACHE = re.compile(r"<!-- (?:commits|bot) cache: (.*) -->", re.DOTALL)
REGEX_IGNORE_COMMIT_COUNT = r"\+commit-count"
REGEX_IGNORE_FILE_COUNT = r"\+file-count"
TEST_WAIT_GAP = 720
ALL_CHECK_FUNCTIONS = None
ALL_GPU_FLAVORS = [
    x.strip() for x in open(join(dirname(__file__), "gpu_flavors.txt"), "r").read().splitlines()
]
EXTRA_RELVALS_TESTS = ["threading", "gpu", "high_stats", "nano"] + ALL_GPU_FLAVORS
EXTRA_RELVALS_TESTS_OPTS = "_" + "|_".join(EXTRA_RELVALS_TESTS)
EXTRA_TESTS = (
    "|".join(EXTRA_RELVALS_TESTS)
    + "|hlt_p2_integration|hlt_p2_timing|profiling|none|multi_microarchs"
)
SKIP_TESTS = "|".join(["static", "header"])
ENABLE_TEST_PTRN = "enable(_test(s|)|)"
JENKINS_NODES = r"[a-zA-Z0-9_|&\s()-]+"
MULTILINE_COMMENTS_MAP = {
    "(workflow|relval)(s|)("
    + EXTRA_RELVALS_TESTS_OPTS
    + "|)": [format(r"%(workflow)s(\s*,\s*%(workflow)s|)*", workflow=WF_PATTERN), "MATRIX_EXTRAS"],
    "(workflow|relval)(s|)_profiling": [
        format(r"%(workflow)s(\s*,\s*%(workflow)s|)*", workflow=WF_PATTERN),
        "PROFILING_WORKFLOWS",
    ],
    "pull_request(s|)": [
        format("%(cms_pr)s(,%(cms_pr)s)*", cms_pr=CMS_PR_PATTERN),
        "PULL_REQUESTS",
    ],
    "full_cmssw|full": ["true|false", "BUILD_FULL_CMSSW"],
    "disable_poison": ["true|false", "DISABLE_POISON"],
    "use_ib_tag": ["true|false", "USE_IB_TAG"],
    "baseline": ["self|default", "USE_BASELINE"],
    "set_env": [r"[A-Z][A-Z0-9_]+(\s*,\s*[A-Z][A-Z0-9_]+|)*", "CMSBOT_SET_ENV"],
    "skip_test(s|)": [format(r"(%(tests)s)(\s*,\s*(%(tests)s))*", tests=SKIP_TESTS), "SKIP_TESTS"],
    "dry_run": ["true|false", "DRY_RUN"],
    "jenkins_(slave|node)": [JENKINS_NODES, "RUN_ON_SLAVE"],
    "(arch(itecture(s|))|release|release/arch)": [CMSSW_RELEASE_QUEUE_PATTERN, "RELEASE_FORMAT"],
    ENABLE_TEST_PTRN: [
        format(r"(%(tests)s)(\s*,\s*(%(tests)s))*", tests=EXTRA_TESTS),
        "ENABLE_BOT_TESTS",
    ],
    "ignore_test(s|)": ["build-warnings|clang-warnings", "IGNORE_BOT_TESTS"],
    "container": [
        "[a-zA-Z][a-zA-Z0-9_-]+/[a-zA-Z][a-zA-Z0-9_-]+(:[a-zA-Z0-9_-]+|)",
        "DOCKER_IMGAGE",
    ],
    "cms-addpkg|addpkg": [
        format("%(pkg)s(,%(pkg)s)*", pkg=CMSSW_PACKAGE_PATTERN),
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

BOT_CACHE_CHUNK_SIZE = 55000
TOO_MANY_COMMITS_WARN_THRESHOLD = 150
TOO_MANY_COMMITS_FAIL_THRESHOLD = 240
TOO_MANY_FILES_WARN_THRESHOLD = 1500
TOO_MANY_FILES_FAIL_THRESHOLD = 3001
CHANGED_FILES_FROM_DIFF_THRESHOLD = 500
L2_DATA = {}

logger: logging.Logger


def setup_logging(loglevel):
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {loglevel}")

    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(numeric_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter("%(filename)s:%(lineno)d [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


from github import Commit

create_status = True
original__create_status = Commit.Commit.create_status


def my_create_status(*args, **kwargs):
    if create_status:
        original__create_status(*args, **kwargs)


Commit.Commit.create_status = my_create_status


def update_CMSSW_LABELS(repo_config):
    try:
        check_dpg_pog = repo_config.CHECK_DPG_POG
    except:
        check_dpg_pog = False
    dpg_pog = {} if not check_dpg_pog else get_dpg_pog()
    for l in CMSSW_LABELS.keys():
        if check_dpg_pog and (not l in dpg_pog) and (not l in TYPE_COMMANDS):
            del CMSSW_LABELS[l]
        else:
            CMSSW_LABELS[l] = [
                re.compile("^(" + p + ").*$") if isinstance(p, str) else p for p in CMSSW_LABELS[l]
            ]
    return


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


def collect_commit_cache(bot_cache):
    REGEX_COMMIT_SHA = re.compile("^[a-f0-9]{40}$", re.IGNORECASE)
    commit_cache = {k: v for k, v in bot_cache.items() if REGEX_COMMIT_SHA.match(k)}
    if commit_cache:
        for k in commit_cache:
            del bot_cache[k]
        bot_cache["commits"] = commit_cache


def read_bot_cache(data):
    logger.info("Loading bot cache")
    res = loads_maybe_decompress(data)
    for k, v in BOT_CACHE_TEMPLATE.items():
        if k not in res:
            res[k] = copy.deepcopy(v)
    collect_commit_cache(res)
    return res


def extract_bot_cache(comment_msgs):
    logger.debug(
        "Reading bot cache from technical comment(s): %s",
        ",".join(str(c) for c in comment_msgs),
    )

    data = ""
    for comment_msg in comment_msgs:
        seen_commits_match = REGEX_COMMITS_CACHE.search(comment_msg.body)
        if seen_commits_match:
            data += seen_commits_match[1]

    if data:
        res = read_bot_cache(data)
        logger.debug("Loaded bot cache:\n%s", dumps(res))
        return res

    return {}


def prepare_bot_cache(bot_cache):
    res = []
    data = dumps_maybe_compress(bot_cache)
    while data:
        # The limit is 65535 chars, and minimal bot cache comment is
        # `cms-bot internal usage<!-- bot cache:  -->`, 42 characters.
        # But since the cache can be embedded in an "already seen" comment, whose length is not
        # known in advance, we limit the amout of (encoded cache) data per comment
        # to BOT_CACHE_CHUNK_SIZE chars.
        part, data = data[:BOT_CACHE_CHUNK_SIZE], data[BOT_CACHE_CHUNK_SIZE:]
        res.append(part)

    return res


def write_bot_cache(bot_cache, cache_comments, issue, dryRun):
    logger.debug("Save bot cache: %s", dumps(bot_cache))
    data = prepare_bot_cache(bot_cache)
    for i, part in enumerate(data):
        try:
            cache_comment = cache_comments[i]
        except (TypeError, IndexError):
            cache_comment = None

        old_body = cache_comment.body if cache_comment else CMSBOT_TECHNICAL_MSG
        new_body = REGEX_COMMITS_CACHE.sub("", old_body) + "<!-- bot cache: " + part + " -->"
        if old_body == new_body:
            continue

        logger.info("Saving bot cache (%s/%s)", i + 1, len(data))
        if not dryRun:
            if cache_comment:
                cache_comment.edit(new_body)
            else:
                issue.create_comment(new_body)
        else:
            if cache_comment:
                logger.info("DRY RUN: Updating existing comment with text")
            else:
                logger.info("DRY RUN: Creating technical comment with text")
            logger.debug(new_body.encode("ascii", "ignore").decode())

    # If new commit cache is smaller than previous one, cleanup old technical comments
    if len(data) < len(cache_comments):
        for i in range(len(data), len(cache_comments)):
            logger.debug(
                "Deleting bot cache comment (%s/%s)",
                i + 1 - len(data),
                len(cache_comments) - len(data),
            )
            if not dryRun:
                cache_comments[i].delete()


def get_commenter_categories(commenter, comment_date):
    if commenter not in L2_DATA:
        return []
    for item in L2_DATA[commenter]:
        if comment_date < item["start_date"]:
            return []
        if ("end_date" not in item) or (comment_date < item["end_date"]):
            return item["category"]
    return []


def get_package_categories(package):
    cats = []
    for cat, packages in list(CMSSW_CATEGORIES.items()):
        if package in packages:
            cats.append(cat)
    return cats


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


#
# creates a properties file to trigger the test of the pull request
#


def create_properties_file_tests(
    repository, pr_number, parameters, dryRun, abort=False, req_type="tests", repo_config=None
):
    if abort:
        req_type = "abort"
    repo_parts = repository.split("/")
    if req_type in "tests":
        try:
            if not repo_parts[0] in EXTERNAL_REPOS:
                req_type = "user-" + req_type
            elif not repo_config.CMS_STANDARD_TESTS:
                req_type = "user-" + req_type
        except:
            pass
    out_file_name = "trigger-%s-%s-%s.properties" % (
        req_type,
        repository.replace("/", "-"),
        pr_number,
    )

    try:
        if repo_config.JENKINS_SLAVE_LABEL:
            parameters["RUN_LABEL"] = repo_config.JENKINS_SLAVE_LABEL
    except:
        pass
    logger.debug("PropertyFile: %s", out_file_name)
    logger.debug("Data: %s", parameters)
    create_property_file(out_file_name, parameters, dryRun)


def create_property_file(out_file_name, parameters, dryRun):
    if dryRun:
        logger.info("Not creating properties file (dry-run): %s", out_file_name)
        return
    logger.info("Creating properties file %s", out_file_name)
    out_file = open(out_file_name, "w")
    for k in parameters:
        out_file.write("%s=%s\n" % (k, parameters[k]))
    out_file.close()


# Update the milestone for a given issue.
def updateMilestone(repo, issue, pr, dryRun):
    milestoneId = RELEASE_BRANCH_MILESTONE.get(pr.base.label.split(":")[1], None)
    if not milestoneId:
        logger.error("Unable to find a milestone for the given branch")
        return
    if pr.state != "open":
        logger.error("PR not open, not setting/checking milestone")
        return
    if issue.milestone and issue.milestone.number == milestoneId:
        return
    milestone = repo.get_milestone(milestoneId)
    logger.info("Setting milestone to %s", milestone.title)
    if dryRun:
        return
    issue.edit(milestone=milestone)


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
        logger.debug("Matched comment from %s with comment id %s", comment.user.login, comment.id)
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
            logger.info("Message updated")
    return 0


# github_utils.set_issue_emoji -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/Issue.py#L569
# github_utils.set_comment_emoji -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/IssueComment.py#L149
# github_utils.delete_issue_emoji -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/Issue.py#L587
# github_utils.delete_comment_emoji -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/IssueComment.py#L168
def set_emoji(repository, comment, emoji, reset_other):
    if reset_other:
        for e in comment.get_reactions():
            login = e.user.login.encode("ascii", "ignore").decode()
            if login == get_gh_user() and e.content != emoji:
                comment.delete_reaction(e.id)

    comment.create_reaction(emoji)


def set_comment_emoji_cache(dryRun, bot_cache, comment, repository, emoji="+1", reset_other=True):
    if dryRun:
        return
    comment_id = str(comment.id)
    if (
        (not comment_id in bot_cache["emoji"])
        or (bot_cache["emoji"][comment_id] != emoji)
        or (comment.reactions[emoji] == 0)
    ):
        set_emoji(repository, comment, emoji, reset_other)
        bot_cache["emoji"][comment_id] = emoji
    return


def has_user_emoji(bot_cache, comment, repository, emoji, user):
    e = None
    comment_id = str(comment.id)
    if (comment_id in bot_cache["emoji"]) and (comment.reactions[emoji] > 0):
        e = bot_cache["emoji"][comment_id]
    else:
        # github_utils.get_issue_emojis -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/Issue.py#L556
        # github_utils.get_comment_emojis -> https://github.com/PyGithub/PyGithub/blob/v1.56/github/IssueComment.py#L135
        emojis = comment.get_reactions()
        for x in emojis:
            if x["user"]["login"].encode("ascii", "ignore").decode() == user:
                e = x["content"]
                bot_cache["emoji"][comment_id] = x
                break
    return e and e == emoji


def get_assign_categories(line, extra_labels):
    m = re.match(
        r"^\s*(New categories assigned:\s*|(unassign|assign)\s+(from\s+|package\s+|))([a-zA-Z0-9/,\s-]+)\s*$",
        line,
        re.I,
    )
    if m:
        assgin_type = m.group(1).lower()
        if m.group(2):
            assgin_type = m.group(2).lower()
        new_cats = []
        for ex_cat in m.group(4).replace(" ", "").split(","):
            if "/" in ex_cat:
                new_cats += get_package_categories(ex_cat)
                add_nonblocking_labels([ex_cat], extra_labels)
                continue
            if not ex_cat in CMSSW_CATEGORIES:
                continue
            new_cats.append(ex_cat)
        return (assgin_type.strip(), new_cats)
    return ("", [])


def ignore_issue(repo_config, repo, issue):
    ig_issues = getattr(repo_config, "IGNORE_ISSUES", {})
    if issue.number in ig_issues:
        return True
    if (repo.full_name in ig_issues) and (issue.number in ig_issues[repo.full_name]):
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


def check_extra_labels(first_line, extra_labels):
    if "urgent" in first_line:
        extra_labels["urgent"] = ["urgent"]
    elif "backport" in first_line:
        bp_pr = ""
        if "#" in first_line:
            bp_pr = first_line.split("#", 1)[1].strip()
        else:
            bp_pr = first_line.split("/pull/", 1)[1].strip("/").strip()
        extra_labels["backport"] = ["backport", bp_pr]


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
        if not ltype in extra_labels:
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


def check_ignore_bot_tests(first_line, *args):
    return first_line.upper().replace(" ", ""), None


def check_enable_bot_tests(first_line, *args):
    tests = first_line.upper().replace(" ", "")
    if "NONE" in tests:
        tests = "NONE"
    return tests, None


def check_extra_matrix_args(first_line, repo, params, mkey, param, *args):
    kitem = mkey.split("_")
    logger.debug(
        "check_extra_matrix_args called with: first_line=%s, repo=%s, params=%s, mkey=%s, param=%s",
        first_line,
        repo,
        params,
        mkey,
        param,
    )
    if kitem[-1] in ["input"] + EXTRA_RELVALS_TESTS:
        param = param + "_" + kitem[-1].upper().replace("-", "_")
    logger.debug("check_extra_matrix_args: first_line=%s, param=%s", first_line, param)
    return first_line, param


def check_matrix_extras(first_line, repo, params, mkey, param, *args):
    kitem = mkey.split("_")
    logger.debug(
        "check_matrix_extras called with: first_line=%s, repo=%s, params=%s, mkey=%s, param=%s",
        first_line,
        repo,
        params,
        mkey,
        param,
    )
    if kitem[-1] in EXTRA_RELVALS_TESTS:
        param = param + "_" + kitem[-1].upper().replace("-", "_")
    first_line = ",".join(sorted(first_line.split(",")))
    logger.debug("check_extra_matrix_args: first_line=%s, param=%s", first_line, param)
    return first_line, param


def check_pull_requests(first_line, repo, *args):
    return " ".join(get_prs_list_from_string(first_line, repo)), None


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


def check_test_cmd(first_line, repo, params):
    m = REGEX_TEST_REG.match(first_line)
    if m:
        wfs = ""
        prs = []
        cmssw_que = ""
        logger.debug("check_test_cmd: %s", m.groups())
        if m.group(6):
            wfs = ",".join(set(m.group(6).replace(" ", "").split(",")))
        if m.group(11):
            prs = get_prs_list_from_string(m.group(11), repo)
        if m.group(20):
            cmssw_que = m.group(20)
        if m.group(25):
            if "addpkg" in m.group(25):
                params["EXTRA_CMSSW_PACKAGES"] = m.group(27).strip()
            else:
                params["BUILD_FULL_CMSSW"] = "true"
        return (True, " ".join(prs), wfs, cmssw_que)
    return (False, "", "", "")


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


def parse_extra_params(full_comment, repo):
    global ALL_CHECK_FUNCTIONS
    xerrors = {"format": [], "key": [], "value": []}
    matched_extra_args = {}
    if ALL_CHECK_FUNCTIONS is None:
        all_globals = globals()
        ALL_CHECK_FUNCTIONS = dict(
            [
                (f, all_globals[f])
                for f in all_globals
                if f.startswith("check_") and callable(all_globals[f])
            ]
        )
    for l in full_comment[1:]:
        l = l.strip()
        if l.startswith("-"):
            l = l[1:]
        elif l.startswith("*"):
            l = l[1:]
        l = l.strip()
        if l == "":
            continue
        if not "=" in l:
            xerrors["format"].append("'%s'" % l)
            continue
        line_args = l.split("=", 1)
        line_args[0] = line_args[0].replace(" ", "")
        line_args[1] = line_args[1].strip()
        found = False
        for k, pttrn in MULTILINE_COMMENTS_MAP.items():
            if not re.match("^(%s)$" % k, line_args[0], re.I):
                continue
            if (len(pttrn) < 3) or (not pttrn[2]):
                line_args[1] = line_args[1].replace(" ", "")
            param = pttrn[1]
            if not re.match("^(%s)$" % pttrn[0], line_args[1], re.I):
                xerrors["value"].append(line_args[0])
                found = True
                break
            try:
                func = "check_%s" % param.lower()
                if func in ALL_CHECK_FUNCTIONS:
                    line_args[1], new_param = ALL_CHECK_FUNCTIONS[func](
                        line_args[1], repo, matched_extra_args, line_args[0], param
                    )
                    if new_param:
                        param = new_param
            except:
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
    return matched_extra_args


def multiline_check_function(first_line, comment_lines, repository):
    if first_line.lower() not in ["test parameters", "test parameters:"]:
        return False, {}, ""
    extra_params = parse_extra_params(comment_lines, repository)
    logger.debug("multiline_check_function: extra_params=%s", extra_params)
    if "errors" in extra_params:
        return False, {}, extra_params["errors"]
    return True, extra_params, ""


def get_changed_files(repo, pr, use_gh_patch=False):
    if (not use_gh_patch) and (pr.changed_files <= CHANGED_FILES_FROM_DIFF_THRESHOLD):
        pr_files = []
        for f in pr.get_files():
            pr_files.append(f.filename)
            try:
                if f.previous_filename:
                    pr_files.append(f.previous_filename)
            except:
                pass
        logger.info("PR Files: %s", pr_files)
        return pr_files
    diff_url = "https://patch-diff.githubusercontent.com/raw/{}/pull/{}.diff".format(
        repo.full_name, pr.number
    )
    cmd = (
        "curl -s -L %s | grep '^diff --git ' | sed 's|.* a/||;s|  *b/| |' | tr ' ' '\n' | sort | uniq"
        % diff_url
    )
    e, o = run_cmd(cmd)
    if e:
        logger.error("Request to %s failed", diff_url)
        logger.error(e)
        exit(1)
    if o:
        return o.split("\n")
    else:
        logger.error("Request to %s did not return any changes, is the PR too big?", diff_url)
        exit(1)


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
    if len(json_) > BOT_CACHE_CHUNK_SIZE:
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
                    if not "mtype" in extra_labels:
                        extra_labels["mtype"] = []
                    extra_labels["mtype"].append(ex_lab)
                    logger.debug("Non-Blocking label:%s:%s:%s", ex_lab, regex.pattern, pkg_file)
                    break
    if ("mtype" in extra_labels) and (not extra_labels["mtype"]):
        del extra_labels["mtype"]
    logger.info("Extra non-blocking labels: %s", extra_labels)
    return


# TODO: remove once we update pygithub
def get_commit_files(repo_, commit):
    return (x["filename"] for x in get_commit(repo_.full_name, commit.sha)["files"])


def on_labels_changed(added_labels, removed_labels):
    # Placeholder function replaced during testing
    pass


def fetch_pr_result(url):
    e, o = run_cmd("curl -k -s -L --max-time 60 %s" % url)
    return e, o


def preprocess_comment_text(comment_msg):
    comment_lines = [l.strip() for l in comment_msg.split("\n") if l.strip()]
    # comment_lines = [re.sub(r"\s{2,}", " ", x) for x in comment_lines]
    # comment_lines = [re.sub(r"^(?:@?cmsbuild\s*[,]*\s+)?(?:please\s*[,]*\s+)?", "", x) for x in comment_lines]
    return comment_lines


def ensure_ascii(string):
    return string.encode("ascii", "replace").decode("ascii", "replace")


def process_pr(repo_config, gh, repo, issue, dryRun, cmsbuild_user=None, force=False):
    global L2_DATA, create_status
    if (not force) and ignore_issue(repo_config, repo, issue):
        return

    setup_logging("debug")

    gh_user_char = "@"

    if not notify_user(issue):
        gh_user_char = ""

    api_rate_limits(gh)
    prId = issue.number
    repository = repo.full_name
    repo_org, repo_name = repository.split("/", 1)
    auto_test_repo = AUTO_TEST_REPOS
    try:
        if repo_config.AUTO_TEST_REPOS:
            auto_test_repo = [repository]
        else:
            auto_test_repo = []
    except:
        pass
    if not cmsbuild_user:
        cmsbuild_user = repo_config.CMSBUILD_USER
    logger.info(
        "Working on %s for PR/Issue %s with admin user %s", repo.full_name, prId, cmsbuild_user
    )
    logger.info("Notify User: %s", gh_user_char)
    update_CMSSW_LABELS(repo_config)
    set_gh_user(cmsbuild_user)
    cmssw_repo = repo_name == GH_CMSSW_REPO
    cms_repo = repo_org in EXTERNAL_REPOS
    external_repo = (repository != CMSSW_REPO_NAME) and (
        len([e for e in EXTERNAL_REPOS if repo_org == e]) > 0
    )
    create_test_property = False
    repo_cache = {repository: repo}
    packages = set([])
    chg_files = []
    package_categories = {}
    extra_labels = {"mtype": []}
    state_labels = {}
    add_external_category = False
    signing_categories = set([])
    new_package_message = ""
    mustClose = False
    reOpen = False
    releaseManagers = []
    signatures = {}
    watchers = []
    # Process Pull Request
    pkg_categories = set([])
    REGEX_TYPE_CMDS = (
        r"^(type|(build-|)state)\s+(([-+]|)[a-z][a-z0-9_-]+)(\s*,\s*([-+]|)[a-z][a-z0-9_-]+)*$"
    )
    REGEX_EX_CMDS = r"^urgent$|^backport\s+(of\s+|)(#|http(s|):/+github\.com/+%s/+pull/+)\d+$" % (
        repo.full_name
    )
    known_ignore_tests = "%s" % MULTILINE_COMMENTS_MAP["ignore_test(s|)"][0]
    REGEX_EX_IGNORE_CHKS = r"^ignore\s+((%s)(\s*,\s*(%s))*|none)$" % (
        known_ignore_tests,
        known_ignore_tests,
    )
    REGEX_EX_ENABLE_TESTS = r"^enable\s+(%s)$" % MULTILINE_COMMENTS_MAP[ENABLE_TEST_PTRN][0]
    L2_DATA = init_l2_data(repo_config, cms_repo)
    last_commit_date = None
    last_commit_obj = None
    push_test_issue = False
    requestor = ensure_ascii(issue.user.login)
    ignore_tests = ""
    enable_tests = ""
    commit_statuses = None
    bot_status_name = "bot/jenkins"
    bot_ack_name = "bot/ack"
    bot_test_param_name = "bot/test_parameters"
    cms_status_prefix = "cms"
    bot_status = None
    code_checks_status = []
    pre_checks_state = {}
    default_pre_checks = ["code-checks"]
    # For future pre_checks
    # if prId>=somePRNumber: default_pre_checks+=["some","new","checks"]
    pre_checks_url = {}
    events = defaultdict(list)
    all_commits = []
    all_commit_shas = set()
    ok_too_many_commits = False
    warned_too_many_commits = False
    ok_too_many_files = False
    warned_too_many_files = False
    is_draft_pr = False

    if issue.pull_request:
        pr = repo.get_pull(prId)
        if pr.changed_files == 0:
            logger.error("Ignoring: PR with no files changed")
            return
        if pr.draft:
            logger.warning("Draft PR, mentions turned off")
            is_draft_pr = True
            gh_user_char = ""
        if cmssw_repo and cms_repo and (pr.base.ref == CMSSW_DEVEL_BRANCH):
            if pr.state != "closed":
                logger.error("This pull request must go in to master branch")
                if not dryRun:
                    edit_pr(repo.full_name, prId, base="master")
                    msg = format(
                        "%(gh_user_char)s%(user)s, %(dev_branch)s branch is closed for direct updates. cms-bot is going to move this PR to master branch.\n"
                        "In future, please use cmssw master branch to submit your changes.\n",
                        user=requestor,
                        gh_user_char=gh_user_char,
                        dev_branch=CMSSW_DEVEL_BRANCH,
                    )
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
            packages = set(["externals/" + repository])
            ex_pkg = external_to_package(repository)
            if ex_pkg:
                packages.add(ex_pkg)
            if (repo_org != GH_CMSSW_ORGANIZATION) or (repo_name in VALID_CMS_SW_REPOS_FOR_TESTS):
                create_test_property = True
            if (repo_name == GH_CMSDIST_REPO) and (
                not re.match(VALID_CMSDIST_BRANCHES, pr.base.ref)
            ):
                logger.error("Skipping PR as it does not belong to valid CMSDIST branch")
                return
            try:
                if repo_config.NONBLOCKING_LABELS:
                    chg_files = get_changed_files(repo, pr)
                    add_nonblocking_labels(chg_files, extra_labels)
            except:
                pass

        if pr.state == "closed":
            create_test_property = False

        logger.info("Following packages affected: %s", ", ".join(packages))
        for package in packages:
            package_categories[package] = set([])
            for category in get_package_categories(package):
                package_categories[package].add(category)
                pkg_categories.add(category)
        signing_categories.update(pkg_categories)

        # For PR, we always require tests.
        signing_categories.add("tests")
        if add_external_category:
            signing_categories.add("externals")
        if cms_repo:
            logger.info("This pull request requires ORP approval")
            signing_categories.add("orp")

        logger.info("Following categories affected: %s", ", ".join(signing_categories))

        if cmssw_repo:
            # If there is a new package, add also a dummy "new" category.
            all_packages = [
                package
                for category_packages in list(CMSSW_CATEGORIES.values())
                for package in category_packages
            ]
            has_category = all([package in all_packages for package in packages])
            if not has_category:
                new_package_message = "\nThe following packages do not have a category, yet:\n\n"
                new_package_message += (
                    "\n".join([package for package in packages if not package in all_packages])
                    + "\n"
                )
                new_package_message += "Please create a PR for https://github.com/cms-sw/cms-bot/blob/master/categories_map.py to assign category\n"
                logger.debug(new_package_message)
                signing_categories.add("new-package")

        # Add watchers.yaml information to the WATCHERS dict.
        WATCHERS = read_repo_file(repo_config, "watchers.yaml", {})
        # Given the files modified by the PR, check if there are additional developers watching one or more.
        author = pr.user.login
        watchers = set(
            [
                user
                for chg_file in chg_files
                for user, watched_regexp in list(WATCHERS.items())
                for regexp in watched_regexp
                if re.match("^" + regexp + ".*", chg_file) and user != author
            ]
        )
        # Handle category watchers
        catWatchers = read_repo_file(repo_config, "category-watchers.yaml", {})
        non_block_cats = [] if not "mtype" in extra_labels else extra_labels["mtype"]
        for user, cats in list(catWatchers.items()):
            for cat in cats:
                if (cat in signing_categories) or (cat in non_block_cats):
                    logger.debug("Added %s to watch due to cat %s", user, cat)
                    watchers.add(user)

        # Handle watchers
        watchingGroups = read_repo_file(repo_config, "groups.yaml", {})
        for watcher in [x for x in watchers]:
            if not watcher in watchingGroups:
                continue
            watchers.remove(watcher)
            watchers.update(set(watchingGroups[watcher]))
        watchers = set([gh_user_char + u for u in watchers])
        logger.info("Watchers: %s", ", ".join(watchers))

        all_commits = get_pr_commits_reversed(pr)
        all_commit_shas = {commit.sha for commit in all_commits}

        if all_commits:
            last_commit_obj = all_commits[0]
        else:
            return

        last_commit = last_commit_obj.commit
        commit_statuses = last_commit_obj.get_combined_status().statuses
        bot_status = get_status(bot_status_name, commit_statuses)
        if not bot_status:
            bot_status_name = "bot/%s/jenkins" % prId
            bot_ack_name = "bot/%s/ack" % prId
            bot_test_param_name = "bot/%s/test_parameters" % prId
            cms_status_prefix = "cms/%s" % prId
            bot_status = get_status(bot_status_name, commit_statuses)
        code_checks_status = [
            s for s in commit_statuses if s.context == "%s/code-checks" % cms_status_prefix
        ]
        logger.info("PR Statuses (%s total): %s", len(commit_statuses), commit_statuses)
        last_commit_date = last_commit.committer.date

        logger.info(
            "Latest commit by %s at %s",
            ensure_ascii(last_commit.committer.name),
            last_commit_date,
        )
        logger.info("Latest commit message: %s", ensure_ascii(last_commit.message))
        logger.info("Latest commit sha: %s", last_commit.sha)
        logger.info("PR update time: %s", pr.updated_at)
        logger.info("Time UTC: %s", datetime.utcnow())
        if last_commit_date > datetime.utcnow():
            logger.warning("==== Future commit found ====")
            add_labels = True
            try:
                add_labels = repo_config.ADD_LABELS
            except:
                pass
            if (not dryRun) and add_labels:
                labels = [ensure_ascii(x.name) for x in issue.labels]
                if not "future-commit" in labels:
                    labels.append("future-commit")
                    issue.edit(labels=labels)
            return
        extra_rm = get_release_managers(pr.base.ref)
        if repository == CMSDIST_REPO_NAME:
            br = "_".join(pr.base.ref.split("/")[:2][-1].split("_")[:3]) + "_X"
            if br:
                extra_rm = extra_rm + get_release_managers(br)
        releaseManagers = list(set(extra_rm + CMSSW_ORP))
    else:
        try:
            if (
                (repo_config.OPEN_ISSUE_FOR_PUSH_TESTS)
                and (requestor == cmsbuild_user)
                and re.match(PUSH_TEST_ISSUE_MSG, issue.title)
            ):
                signing_categories.add("tests")
                push_test_issue = True
        except:
            pass
        if repository == CMSSW_REPO_NAME and re.match(CREATE_REPO, issue.title):
            with open("query-new-data-repo-issues-" + str(issue.number) + ".properties", "w") as f:
                f.write("ISSUE_NUMBER=" + str(issue.number) + "\n")

    # Process the issue comments
    signatures = dict([(x, "pending") for x in signing_categories])
    extra_pre_checks = []
    pre_checks = []
    if issue.pull_request:
        pre_checks = [c for c in signing_categories if c in default_pre_checks]
        for pre_check in pre_checks + ["code-checks"]:
            pre_checks_state[pre_check] = get_status_state(
                "%s/%s" % (cms_status_prefix, pre_check), commit_statuses
            )
        logger.debug("Pre check status: %s", pre_checks_state)
    already_seen = None
    technical_comments = []
    pull_request_updated = False
    comparison_done = False
    comparison_notrun = False
    mustMerge = False
    release_queue = ""
    release_arch = ""
    cmssw_prs = ""
    extra_wfs = ""
    global_test_params = {}
    assign_cats = {}
    hold = {}
    last_test_start_time = None
    abort_test = None
    need_external = False
    backport_pr_num = ""
    comp_warnings = False
    extra_testers = []
    all_comments = [issue]
    code_checks_tools = ""
    new_bot_tests = True
    test_comment = None
    trigger_test = False
    ack_comment = None
    test_params_msg = ""
    test_params_comment = None
    code_check_apply_patch = False
    override_tests_failure = None
    bot_cache = {}
    old_labels = set(ensure_ascii(x.name) for x in issue.labels)

    # start of parsing comments to find the bot_cache
    # to use information during the actual comment loop
    for comment in issue.get_comments():
        all_comments.append(comment)
        if ensure_ascii(comment.user.login) != cmsbuild_user:
            continue
        comment_msg = ensure_ascii(comment.body) if comment.body else ""
        first_line = "".join([l.strip() for l in comment_msg.split("\n") if l.strip()][0:1])
        if (not already_seen) and re.match(ISSUE_SEEN_MSG, first_line):
            already_seen = comment
            if REGEX_COMMITS_CACHE.search(comment_msg):
                technical_comments.append(comment)
        elif re.match(CMSBOT_TECHNICAL_MSG, first_line):
            technical_comments.append(comment)

    if technical_comments:
        if is_draft_pr:
            pull_request_updated = technical_comments[0].created_at < last_commit_date
        bot_cache = extract_bot_cache(technical_comments)

    # Make sure bot cache has the needed keys
    for k, v in BOT_CACHE_TEMPLATE.items():
        if k not in bot_cache:
            bot_cache[k] = copy.deepcopy(v)

    for comment in all_comments:
        ack_comment = comment
        commenter = ensure_ascii(comment.user.login)
        commenter_categories = get_commenter_categories(
            commenter, int(comment.created_at.strftime("%s"))
        )
        valid_commenter = (commenter in TRIGGER_PR_TESTS + releaseManagers + [repo_org]) or (
            len(commenter_categories) > 0
        )
        if (not valid_commenter) and (requestor != commenter):
            continue
        comment_msg = ensure_ascii(comment.body) if comment.body else ""
        # The first line is an invariant.
        comment_lines = preprocess_comment_text(comment_msg)
        first_line = "".join(comment_lines[0:1])
        if commenter == cmsbuild_user:
            if re.match(ISSUE_SEEN_MSG, first_line):
                if not already_seen:
                    already_seen = comment
                backport_pr_num = get_backported_pr(comment_msg)
                if issue.pull_request and last_commit_date:
                    pull_request_updated = comment.created_at < last_commit_date
                continue

            if re.match("^" + HOLD_MSG + ".+", first_line):
                for u in first_line.split(HOLD_MSG, 2)[1].split(","):
                    u = u.strip().lstrip("@")
                    if u in hold:
                        hold[u] = 0
                continue

        assign_type, new_cats = get_assign_categories(first_line, extra_labels)
        if new_cats:
            if (assign_type == "new categories assigned:") and (commenter == cmsbuild_user):
                for ex_cat in new_cats:
                    if ex_cat in assign_cats:
                        assign_cats[ex_cat] = 1
            elif commenter_categories or (commenter in CMSSW_ISSUES_TRACKERS):
                set_comment_emoji_cache(dryRun, bot_cache, comment, repository)
                if assign_type == "assign":
                    for ex_cat in new_cats:
                        if not ex_cat in signing_categories:
                            assign_cats[ex_cat] = 0
                            signing_categories.add(ex_cat)
                            signatures[ex_cat] = "pending"
                elif assign_type == "unassign":
                    for ex_cat in new_cats:
                        if ex_cat in assign_cats:
                            assign_cats.pop(ex_cat)
                            signing_categories.remove(ex_cat)
                            signatures.pop(ex_cat)
            continue

        # Some of the special users can say "hold" prevent automatic merging of
        # fully signed PRs.
        comment_emoji = ""
        if re.match("^hold$", first_line, re.I):
            comment_emoji = "-1"
            if commenter_categories or (commenter in releaseManagers + PR_HOLD_MANAGERS):
                hold[commenter] = 1
                comment_emoji = "+1"
        elif re.match(REGEX_EX_CMDS, first_line, re.I):
            comment_emoji = "-1"
            if commenter_categories or (commenter in releaseManagers + [requestor]):
                check_extra_labels(first_line.lower(), extra_labels)
                comment_emoji = "+1"
        elif re.match(REGEX_TYPE_CMDS, first_line, re.I):
            comment_emoji = "-1"
            if commenter_categories or (commenter in releaseManagers + [requestor]):
                comment_emoji = (
                    "+1"
                    if check_type_labels(first_line.lower(), extra_labels, state_labels)
                    else "-1"
                )
        elif re.match(REGEX_EX_IGNORE_CHKS, first_line, re.I):
            comment_emoji = "-1"
            if valid_commenter:
                ignore_tests = check_ignore_bot_tests(first_line.split(" ", 1)[-1])
                comment_emoji = "+1"
        elif re.match(REGEX_EX_ENABLE_TESTS, first_line, re.I):
            comment_emoji = "-1"
            if valid_commenter:
                enable_tests, _ = check_enable_bot_tests(first_line.split(" ", 1)[-1])
                comment_emoji = "+1"
        elif re.match(r"^allow\s+@([^ ]+)\s+test\s+rights$", first_line, re.I):
            comment_emoji = "-1"
            if commenter_categories or (commenter in releaseManagers):
                tester = first_line.split("@", 1)[-1].split(" ", 1)[0]
                if not tester in TRIGGER_PR_TESTS:
                    TRIGGER_PR_TESTS.append(tester)
                    extra_testers.append(tester)
                    logger.info("Added user in test category: %s", tester)
                comment_emoji = "+1"
        elif re.match("^unhold$", first_line, re.I):
            comment_emoji = "-1"
            if "orp" in commenter_categories:
                hold = {}
                comment_emoji = "+1"
            elif commenter_categories or (commenter in releaseManagers + PR_HOLD_MANAGERS):
                if commenter in hold:
                    del hold[commenter]
                    comment_emoji = "+1"
        elif CLOSE_REQUEST.match(first_line):
            comment_emoji = "-1"
            if (commenter_categories or (commenter in releaseManagers)) or (
                (not issue.pull_request) and (commenter in CMSSW_ISSUES_TRACKERS)
            ):
                reOpen = False
                if issue.state == "open":
                    mustClose = True
                comment_emoji = "+1"
                logger.info("==> Closing request received from %s", commenter)
        elif REOPEN_REQUEST.match(first_line):
            comment_emoji = "-1"
            if (commenter_categories or (commenter in releaseManagers)) or (
                (not issue.pull_request) and (commenter in CMSSW_ISSUES_TRACKERS)
            ):
                mustClose = False
                if (issue.state == "closed") and (comment.created_at >= issue.closed_at):
                    reOpen = True
                comment_emoji = "+1"
                logger.info("==> Reopen request received from %s", commenter)
        elif re.match(r"^\s*" + REGEX_IGNORE_COMMIT_COUNT + r"\s*$", first_line):
            comment_emoji = "-1"
            if commenter in CMSSW_ISSUES_TRACKERS:
                ok_too_many_commits = pr.commits < TOO_MANY_COMMITS_FAIL_THRESHOLD
                comment_emoji = "+1"
        elif re.match(r"^\s*" + REGEX_IGNORE_FILE_COUNT + r"\s*$", first_line):
            comment_emoji = "-1"
            if commenter in CMSSW_ISSUES_TRACKERS:
                ok_too_many_files = pr.changed_files < TOO_MANY_FILES_FAIL_THRESHOLD
                comment_emoji = "+1"

        if comment_emoji:
            set_comment_emoji_cache(dryRun, bot_cache, comment, repository, emoji=comment_emoji)
            continue

        if valid_commenter:
            valid_multiline_comment, test_params, test_params_m = multiline_check_function(
                first_line, comment_lines, repository
            )
            if test_params_m:
                # Error in parameters
                test_params_msg = str(comment.id) + ":" + test_params_m
                test_params_comment = comment
                continue
            elif valid_multiline_comment:
                test_params_comment = comment
                global_test_params = dict(test_params)
                if "ENABLE_BOT_TESTS" in global_test_params:
                    enable_tests = global_test_params["ENABLE_BOT_TESTS"]
                test_params_msg = str(comment.id) + ":" + dumps(global_test_params, sort_keys=True)
                continue

        if cmssw_repo:
            m = CODE_CHECKS_REGEXP.match(first_line)
            if m:
                first_line = "code-checks"
                code_check_apply_patch = False
                if m.group(1):
                    code_checks_tools = m.group(1).strip().split(" ")[-1]
                if m.group(2):
                    code_check_apply_patch = True
                set_comment_emoji_cache(dryRun, bot_cache, comment, repository, emoji="+1")

        selected_cats = []

        if re.match("^([+]1|approve[d]?|sign|signed)$", first_line, re.I):
            ctype = "+1"
            selected_cats = commenter_categories[:]
        elif re.match("^([-]1|reject|rejected)$", first_line, re.I):
            ctype = "-1"
            selected_cats = commenter_categories[:]
        elif re.match("^[+-][a-z][a-z0-9-]+$", first_line, re.I):
            category_name = first_line[1:].lower()
            if category_name in commenter_categories:
                ctype = first_line[0] + "1"
                selected_cats = [category_name]

        if "orp" in selected_cats:
            # Lines 1281, 1286 of original code
            mustClose = False

        for cat in ["tests", "code-checks"]:
            if cat in selected_cats:
                selected_cats.remove(cat)

        if selected_cats:
            events[comment.created_at].append(
                {
                    "type": "sign",
                    "value": {
                        "ctype": ctype,
                        "selected_cats": selected_cats,
                        "comment": comment,
                    },
                }
            )
            continue

        # Ignore all other messages which are before last commit.
        if issue.pull_request and (comment.created_at < last_commit_date):
            continue

        if cmssw_repo and first_line == "code-checks":
            signatures[first_line] = "pending"
            if first_line not in pre_checks + extra_pre_checks:
                extra_pre_checks.append(first_line)
            if code_checks_status and (code_checks_status[0].updated_at >= comment.created_at):
                continue
            if first_line in pre_checks:
                if (pre_checks_state["code-checks"] in ["pending", ""]) and (
                    not code_checks_status
                ):
                    continue
            elif pre_checks_state["code-checks"] in ["pending"]:
                continue
            pre_checks_state["code-checks"] = ""
            logger.info("Found: Code Checks request %s", code_checks_tools)
            continue

        # Check for cmsbuild_user comments and tests requests only for pull requests
        if commenter == cmsbuild_user:
            if not issue.pull_request and not push_test_issue:
                continue
            if (
                "This PR contains many commits" in first_line
                and pr.commits < TOO_MANY_COMMITS_FAIL_THRESHOLD
            ) or "This PR contains too many commits" in first_line:
                warned_too_many_commits = True
                continue

            if (
                "This PR touches many files" in first_line
                and pr.changed_files < TOO_MANY_FILES_FAIL_THRESHOLD
            ) or "This PR touches too many files" in first_line:
                warned_too_many_files = True
                continue

            sec_line = comment_lines[1:2]
            if not sec_line:
                sec_line = ""
            else:
                sec_line = sec_line[0]
            if re.match("Comparison is ready", first_line):
                if ("tests" in signatures) and signatures["tests"] != "pending":
                    comparison_done = True
            elif "-code-checks" == first_line:
                signatures["code-checks"] = "rejected"
                pre_checks_url["code-checks"] = comment.html_url
            elif "+code-checks" == first_line:
                signatures["code-checks"] = "approved"
                pre_checks_url["code-checks"] = comment.html_url
            elif re.match("^Comparison not run.+", first_line):
                if ("tests" in signatures) and signatures["tests"] != "pending":
                    comparison_notrun = True
            elif re.match(FAILED_TESTS_MSG, first_line) or re.match(
                IGNORING_TESTS_MSG, first_line
            ):
                signatures["tests"] = "pending"
            elif re.match("Pull request ([^ #]+|)[#][0-9]+ was updated[.].*", first_line):
                pull_request_updated = False
            elif re.match(TRIGERING_TESTS_MSG, first_line) or re.match(
                TRIGERING_TESTS_MSG1, first_line
            ):
                signatures["tests"] = "started"
                last_test_start_time = comment.created_at
                abort_test = None
                need_external = False
                if sec_line.startswith("Using externals from cms-sw/cmsdist#"):
                    need_external = True
                elif sec_line.startswith("Tested with other pull request"):
                    need_external = True
                elif sec_line.startswith("Using extra pull request"):
                    need_external = True
            elif re.match(TESTS_RESULTS_MSG, first_line):
                test_sha = sec_line.replace("Tested at: ", "").strip()
                if (
                    (not push_test_issue)
                    and (test_sha != last_commit.sha)
                    and (test_sha != "UNKNOWN")
                    and (not "I had the issue " in first_line)
                ):
                    logger.warning("Ignoring test results for sha: %s", test_sha)
                    continue
                comparison_done = False
                comparison_notrun = False
                comp_warnings = False
                if "+1" in first_line:
                    signatures["tests"] = "approved"
                    comp_warnings = (
                        len([1 for l in comment_lines if "Compilation Warnings: Yes" in l]) > 0
                    )
                    pre_checks_url["tests"] = comment.html_url
                elif "-1" in first_line:
                    signatures["tests"] = "rejected"
                    pre_checks_url["tests"] = comment.html_url
                else:
                    signatures["tests"] = "pending"
                logger.debug(
                    "Previous tests already finished, resetting test request state to %s",
                    signatures["tests"],
                )

        if issue.pull_request or push_test_issue:
            # Check if the release manager asked for merging this.
            if re.match(r"^\s*(merge)\s*$", first_line, re.I):
                emoji = "-1"
                if (commenter in releaseManagers) or ("orp" in commenter_categories):
                    mustMerge = True
                    mustClose = False
                    emoji = "+1"
                    if ("orp" in commenter_categories) and ("orp" in signatures):
                        signatures["orp"] = "approved"
                set_comment_emoji_cache(dryRun, bot_cache, comment, repository, emoji=emoji)
                continue

            # Check if the someone asked to trigger the tests
            if valid_commenter:
                ok, v2, v3, v4 = check_test_cmd(first_line, repository, global_test_params)
                if ok:
                    test_comment = comment
                    abort_test = None
                    cmssw_prs = v2
                    extra_wfs = ",".join(sorted(v3.split(",")))
                    release_queue = v4
                    release_arch = ""
                    if "/" in release_queue:
                        release_queue, release_arch = release_queue.split("/", 1)
                    elif re.match("^" + ARCH_PATTERN + "$", release_queue):
                        release_arch = release_queue
                        release_queue = ""
                    logger.info(
                        "Tests requested: %s asked to test this PR with cmssw_prs=%s, release_queue=%s, arch=%s and workflows=%s",
                        commenter,
                        cmssw_prs,
                        release_queue,
                        release_arch,
                        extra_wfs,
                    )
                    logger.debug("Comment message: %s", first_line)
                    signatures["tests"] = "pending"
                    continue
                elif REGEX_TEST_ABORT.match(first_line) and (signatures["tests"] == "pending"):
                    abort_test = comment
                    test_comment = None
                    signatures["tests"] = "pending"
                    continue
                elif REGEX_TEST_IGNORE.match(first_line):
                    reason = REGEX_TEST_IGNORE.match(first_line)[1].strip()
                    if reason not in TEST_IGNORE_REASON:
                        logger.error("Invalid ignore reason: %s", reason)
                        set_comment_emoji_cache(dryRun, bot_cache, comment, repository, "-1")
                        reason = ""
                    if reason:
                        override_tests_failure = reason
                        set_comment_emoji_cache(dryRun, bot_cache, comment, repository)

    # end of parsing comments section

    # Extract enabled GPU flavors and remove them from enable_tests
    new_enable_tests = []
    enabled_gpu_flavors = set()
    for test in enable_tests.split(","):
        if test == "GPU":
            enabled_gpu_flavors.update([x.upper() for x in ALL_GPU_FLAVORS])
        elif test.lower() in ALL_GPU_FLAVORS:
            enabled_gpu_flavors.add(test)
        else:
            new_enable_tests.append(test)

    new_enable_tests.extend(list(enabled_gpu_flavors))
    enable_tests = ",".join(sorted(new_enable_tests))

    # Check if it needs to be automatically closed.
    if mustClose:
        if issue.state == "open":
            logger.info("This pull request must be closed.")
            if not dryRun:
                issue.edit(state="closed")
    elif reOpen:
        if issue.state == "closed":
            logger.info("This pull request must be reopened.")
            if not dryRun:
                issue.edit(state="open")

    if issue.pull_request:
        if (
            pr.commits >= TOO_MANY_COMMITS_WARN_THRESHOLD
            and (not warned_too_many_commits)
            and (not ok_too_many_commits)
        ):
            if pr.commits < TOO_MANY_COMMITS_FAIL_THRESHOLD:
                if not dryRun:
                    issue.create_comment(
                        "This PR contains many commits ({0} >= {1}) and will not be processed. "
                        "Please ensure you have selected the correct target branch and consider squashing unnecessary commits.\n"
                        "{2}, to re-enable processing of this PR, you can write `+commit-count` in a comment. Thanks.".format(
                            pr.commits,
                            TOO_MANY_COMMITS_WARN_THRESHOLD,
                            ", ".join(
                                sorted([gh_user_char + name for name in CMSSW_ISSUES_TRACKERS])
                            ),
                        )
                    )
            else:
                if not dryRun:
                    issue.create_comment(
                        "This PR contains too many commits ({0} >= {1}) and will not be processed.\n"
                        "Please ensure you have selected the correct target branch and consider squashing unnecessary commits.\n"
                        "The processing of this PR will resume once the commit count drops below the limit.".format(
                            pr.commits,
                            TOO_MANY_COMMITS_FAIL_THRESHOLD,
                        )
                    )

            return

        if pr.commits >= TOO_MANY_COMMITS_WARN_THRESHOLD and not ok_too_many_commits:
            logger.error("Commit count reached and not overridden, quitting")
            return

        if (
            pr.changed_files >= TOO_MANY_FILES_WARN_THRESHOLD
            and (not warned_too_many_files)
            and (not ok_too_many_files)
            and cmssw_repo
        ):
            if pr.changed_files < TOO_MANY_FILES_FAIL_THRESHOLD:
                if not dryRun:
                    issue.create_comment(
                        "This PR touches many files ({0} >= {1}) and will not be processed. "
                        "Please ensure you have selected the correct target branch and consider splitting this PR into several.\n"
                        "{2}, to re-enable processing of this PR, you can write `+file-count` in a comment. Thanks.".format(
                            pr.changed_files,
                            TOO_MANY_FILES_WARN_THRESHOLD,
                            ", ".join([gh_user_char + name for name in CMSSW_ISSUES_TRACKERS]),
                        )
                    )
            else:
                if not dryRun:
                    issue.create_comment(
                        "This PR touches too many files ({0} >= {1}) and will not be processed.\n"
                        "Please ensure you have selected the correct target branch and consider splitting this PR into several.\n"
                        "The processing of this PR will resume once the number of changed files drops below the limit.".format(
                            pr.changed_files,
                            TOO_MANY_FILES_FAIL_THRESHOLD,
                        )
                    )

            return

        if (
            pr.changed_files >= TOO_MANY_FILES_WARN_THRESHOLD
            and not ok_too_many_files
            and cmssw_repo
        ):
            logger.error("Changed file count reached and not overridden, quitting")
            return

        logger.info("Processing commits")

        # Make sure to mark squashed=False if a cached/squashed commit is added back
        for commit_sha in [
            sha
            for sha in all_commit_shas
            if sha in bot_cache["commits"] and bot_cache["commits"][sha].get("squashed", False)
        ]:
            bot_cache["commits"][commit_sha]["squashed"] = False
            logger.warning("A squashed commit %s was unsquashed", commit_sha)

        # "Squashed" flag is used to avoid finding missing commits after we have actually
        # handled the squash
        missing_commits = set(
            k for k in bot_cache["commits"] if not bot_cache["commits"][k].get("squashed", False)
        ).difference(all_commit_shas)
        last_seen_commit_time = None
        new_commits = set()
        files_changed_in_squash = []
        if missing_commits:
            logger.info(
                "Possible squash detected: the following commits were cached, but missing from PR"
            )
            logger.info(str(missing_commits))

            if not "last_seen_sha" in bot_cache:
                bot_cache["last_seen_sha"] = sorted(
                    [
                        (k, bot_cache["commits"][k]["time"])
                        for k in bot_cache["commits"]
                        if not bot_cache["commits"][k].get("squashed", False)
                    ],
                    key=lambda q: q[1],
                )[-1][0]

            last_seen_commit_sha = bot_cache["last_seen_sha"]
            new_head_commit_sha = pr.head.sha
            base_commit_sha = pr.base.sha
            logger.debug(
                "Base sha %s, New head sha %s, last_seen_sha %s",
                base_commit_sha,
                new_head_commit_sha,
                last_seen_commit_sha,
            )

            changes_before_squash = repo.compare(base_commit_sha, last_seen_commit_sha)
            changes_after_squash = repo.compare(base_commit_sha, new_head_commit_sha)

            # Use changed file checksum which is abailable for all files added/removed/modify
            # checksum also works for binary files and renamed files
            # checksum will not work if file is rebased and gets updated contents from upstream
            diff_before_squash = {
                (file.filename, file.sha) for file in changes_before_squash.files
            }
            diff_after_squash = {(file.filename, file.sha) for file in changes_after_squash.files}
            diff_in_squash = diff_before_squash ^ diff_after_squash

            if diff_in_squash:
                logger.warning("PR diff changed, will not preserve signatures")
                files_changed_in_squash = list(set(x[0] for x in diff_in_squash))
            else:
                logger.info("PR diff not changed, preserving signatures and commit statuses")
                last_seen_commit_time = bot_cache["commits"][last_seen_commit_sha]["time"]
            new_commits = all_commit_shas.difference(k for k in bot_cache["commits"])

            # Mark removed commits in cache as squashed
            for commit_sha in missing_commits:
                logger.debug("Marked commit %s as squashed", commit_sha)
                bot_cache["commits"][commit_sha]["squashed"] = True

        bot_cache["last_seen_sha"] = pr.head.sha
        for commit in all_commits:
            if commit.sha not in bot_cache["commits"]:
                bot_cache["commits"][commit.sha] = {
                    "time": int(commit.commit.committer.date.timestamp()),
                    "squashed": False,
                }
                if len(commit.parents) > 1:
                    bot_cache["commits"][commit.sha]["files"] = []
                else:
                    bot_cache["commits"][commit.sha]["files"] = sorted(
                        get_commit_files(repo, commit)
                    )

            elif len(commit.parents) > 1:
                bot_cache["commits"][commit.sha]["files"] = []

            if commit.sha in new_commits:
                bot_cache["commits"][commit.sha]["files"] = files_changed_in_squash
                if last_seen_commit_time:  # clean squash
                    bot_cache["commits"][commit.sha]["time"] = last_seen_commit_time

            cache_entry = bot_cache["commits"][commit.sha]
            events[datetime.fromtimestamp(cache_entry["time"])].append(
                {"type": "commit", "value": {"files": cache_entry["files"], "sha": commit.sha}}
            )

        # Inject events from cached commits
        for commit_sha, cache_entry in bot_cache["commits"].items():
            if cache_entry.get("squashed", False):
                logger.debug("Adding back cached commit %s", commit_sha)
                events[datetime.fromtimestamp(cache_entry["time"])].append(
                    {
                        "type": "commit",
                        "value": {"files": cache_entry["files"], "sha": commit_sha},
                    }
                )

    # Process commits and signatures
    signed_commit_sha = ""
    flattened_eventlist = []
    for _, eventlist in sorted(events.items()):
        flattened_eventlist.extend(eventlist)

    auto_test_comment = None
    for event in flattened_eventlist:
        logger.debug("Event: %s", event)
        if event["type"] == "sign":
            if (not signed_commit_sha) and issue.pull_request:
                continue
            comment = event["value"]["comment"]
            comment_id = str(comment.id)
            cached_signed_commit_sha = bot_cache["signatures"].get(comment_id)
            if cached_signed_commit_sha and cached_signed_commit_sha != signed_commit_sha:
                logger.warning(
                    "Comment %s, cached commit %s doesn't match the present commit %s. "
                    "This comment will be ignored.",
                    comment_id,
                    cached_signed_commit_sha,
                    signed_commit_sha,
                )
                continue

            if cached_signed_commit_sha is None:
                bot_cache["signatures"][comment_id] = signed_commit_sha
            selected_cats = event["value"]["selected_cats"]
            ctype = event["value"]["ctype"]
            if any(x in signing_categories for x in selected_cats):
                set_comment_emoji_cache(dryRun, bot_cache, event["value"]["comment"], repository)

                if ctype == "+1":
                    for sign in selected_cats:
                        signatures[sign] = "approved"
                        if auto_test_comment is None and sign not in (
                            "code-checks",
                            "tests",
                            "orp",
                        ):
                            auto_test_comment = comment
                elif ctype == "-1":
                    for sign in selected_cats:
                        signatures[sign] = "rejected"
            else:
                logger.warning(
                    "Ignoring signature event: %s includes none of %s",
                    selected_cats,
                    signing_categories,
                )
        elif event["type"] == "commit":
            auto_test_comment = None
            # Only signed commits with files
            if event["value"]["files"]:
                signed_commit_sha = event["value"]["sha"]
            if cmssw_repo:
                chg_categories = set()
                for fn in event["value"]["files"]:
                    chg_categories.update(
                        get_package_categories(cmssw_file2Package(repo_config, fn))
                    )

                chg_categories.update(assign_cats.keys())
                for cat in chg_categories:
                    if cat in signing_categories:
                        signatures[cat] = "pending"
            else:
                for cat in signing_categories:
                    signatures[cat] = "pending"
            logger.debug("Signatures: %s", signatures)

    # if (
    #     issue.pull_request
    #     and auto_test_comment
    #     and (test_comment is None)
    #     and ((repository in auto_test_repo) or ("*" in auto_test_repo))
    # ):
    #     test_comment = auto_test_comment

    if push_test_issue:
        auto_close_push_test_issue = True
        try:
            auto_close_push_test_issue = repo_config.AUTO_CLOSE_PUSH_TESTS_ISSUE
        except:
            pass
        if (
            auto_close_push_test_issue
            and (issue.state == "open")
            and ("tests" in signatures)
            and ((signatures["tests"] in ["approved", "rejected"]) or abort_test)
        ):
            logger.info("Closing the issue as it has been tested/aborted")
            if not dryRun:
                issue.edit(state="closed")
        if abort_test:
            job, bnum = get_jenkins_job(issue)
            if job and bnum:
                params = {"JENKINS_PROJECT_TO_KILL": job, "JENKINS_BUILD_NUMBER": bnum}
                create_property_file("trigger-abort-%s" % job, params, dryRun)
        logger.debug("push_test_issue done")
        return

    is_hold = len(hold) > 0
    new_blocker = False
    blockers = ""
    for u in hold:
        blockers += " " + gh_user_char + u + ","
        if hold[u]:
            new_blocker = True
    blockers = blockers.rstrip(",")

    new_assign_cats = []
    for ex_cat in assign_cats:
        if assign_cats[ex_cat] == 1:
            continue
        new_assign_cats.append(ex_cat)

    logger.info("All assigned cats: %s", ",".join(list(assign_cats.keys())))
    logger.info("Newly assigned cats: %s", ",".join(new_assign_cats))
    logger.info("Ignore tests: %s", ignore_tests)
    logger.info("Enable tests: %s", enable_tests)
    logger.info("Tests: %s", cmssw_prs)
    logger.info("Abort: %s", abort_test)
    logger.info("Test comment: %s, bot status %s", test_comment, bot_status)

    dryRunOrig = dryRun
    for cat in pre_checks:
        if (cat in signatures) and (signatures[cat] != "approved"):
            dryRun = True
            break

    old_labels = set(ensure_ascii(x.name) for x in issue.labels)
    logger.info(
        "Stats: backport_pr_num=%s, extra_labels=%s, state_labels=%s",
        backport_pr_num,
        extra_labels,
        state_labels,
    )
    logger.info("Old Labels: %s", sorted(old_labels))
    logger.info("Compilation Warnings: %s", comp_warnings)
    logger.info("Signatures: %s", signatures)
    # Add state labels as mtype labels
    if len(state_labels) != 0:
        if "mtype" in extra_labels:
            extra_labels["mtype"].extend(state_labels.values())
        else:
            extra_labels["mtype"] = list(state_labels.values())
    if "mtype" in extra_labels:
        extra_labels["mtype"] = list(set(extra_labels["mtype"]))
    if "type" in extra_labels:
        extra_labels["type"] = [extra_labels["type"][-1]]

    # Deleting elements if they have no labels
    # FIXME
    # for ltype in extra_labels:
    #    if not extra_labels[ltype]:
    #        del extra_labels[ltype]

    if bot_status is None and issue.state != "open":
        create_status = False

    # Always set test pending label
    if "tests" in signatures:
        if test_comment is not None:
            turl = test_comment.html_url
            if bot_status:
                logger.debug("BOT STATUS:")
                logger.debug("  bot_status=%s", bot_status)
                logger.debug("  bot_status.description=%s", bot_status.description)
                logger.debug("  bot_status.target_url=%s", bot_status.target_url)
                logger.debug("  test_comment.html_url=%s", test_comment.html_url)
            if bot_status and bot_status.description.startswith("Old style tests"):
                new_bot_tests = False
            elif (not bot_status) and (signatures["tests"] != "pending"):
                new_bot_tests = False
            if (not bot_status) or (bot_status.target_url != turl):
                if bot_status or (signatures["tests"] == "pending"):
                    new_bot_tests = True
                    trigger_test = True
                    signatures["tests"] = "started"
                desc = "requested by %s at %s UTC." % (
                    ensure_ascii(test_comment.user.login),
                    test_comment.created_at,
                )
                if not new_bot_tests:
                    desc = "Old style tests %s" % desc
                else:
                    desc = "Tests %s" % desc
                logger.debug('Create status "%s"', desc)
                if not dryRun:
                    last_commit_obj.create_status(
                        "success", description=desc, target_url=turl, context=bot_status_name
                    )
                    set_comment_emoji_cache(dryRun, bot_cache, test_comment, repository)
            if bot_status:
                logger.debug(
                    "bot_status.target_url=%s, turl=%s, signatures['tests']=%s, bot_status.description=%s",
                    bot_status.target_url,
                    turl,
                    signatures["tests"],
                    bot_status.description,
                )
            if (
                bot_status
                and bot_status.target_url == turl
                and signatures["tests"] == "pending"
                and (" requested by " in bot_status.description)
            ):
                signatures["tests"] = "started"
            if (
                get_status_state("%s/unknown/release" % cms_status_prefix, commit_statuses)
                == "error"
            ):
                signatures["tests"] = "pending"
            if signatures["tests"] == "started" and new_bot_tests:
                lab_stats = {}
                for status in commit_statuses:
                    if not status.context.startswith(cms_status_prefix + "/"):
                        continue
                    cdata = status.context.split("/")
                    if cdata[-1] not in ["optional", "required"]:
                        continue
                    if (cdata[-1] not in lab_stats) or (cdata[-1] == "required"):
                        lab_stats[cdata[-1]] = []
                    lab_stats[cdata[-1]].append("pending")
                    if status.state == "pending":
                        continue
                    scontext = "/".join(cdata[:-1])
                    all_states = {}
                    result_url = ""
                    for s in [
                        i
                        for i in commit_statuses
                        if ((i.context == scontext) or (i.context.startswith(scontext + "/")))
                    ]:
                        if (not result_url) and ("/jenkins-artifacts/" in s.target_url):
                            xdata = s.target_url.split("/")
                            while xdata and (not xdata[-2].startswith("PR-")):
                                xdata.pop()
                            if xdata:
                                result_url = "/".join(xdata)
                        if s.context == status.context:
                            continue
                        if s.state not in all_states:
                            all_states[s.state] = []
                        all_states[s.state].append(s.context)
                    logger.debug("Test status for %s: %s", status.context, all_states)
                    if "pending" in all_states:
                        if status.description.startswith("Finished"):
                            logger.info(
                                "Some test might have been restarted for %s. Resetting the status",
                                status.context,
                            )
                            if not dryRun:
                                last_commit_obj.create_status(
                                    "success",
                                    description="OK",
                                    target_url=status.target_url,
                                    context=status.context,
                                )
                        continue
                    if "success" in all_states:
                        lab_stats[cdata[-1]][-1] = "success"
                    if "error" in all_states:
                        if [c for c in all_states["error"] if ("/opt/" not in c)]:
                            lab_stats[cdata[-1]][-1] = "error"
                    logger.info(
                        "Final Status: status.context=%s cdata[-1]=%s lab_stats[cdata[-1]][-1]=%s status.description=%s",
                        status.context,
                        cdata[-1],
                        lab_stats[cdata[-1]][-1],
                        status.description,
                    )
                    if (lab_stats[cdata[-1]][-1] != "pending") and (
                        not status.description.startswith("Finished")
                    ):
                        if result_url:
                            url = (
                                result_url.replace(
                                    "/SDT/jenkins-artifacts/",
                                    "/SDT/cgi-bin/get_pr_results/jenkins-artifacts/",
                                )
                                + "/pr-result"
                            )
                            logger.debug("Fetching PR Result from %s", url)
                            e, o = fetch_pr_result(url)
                            if e:
                                logger.error(o)
                                raise Exception("System-error: unable to get PR result")
                            if o and (not dryRun):
                                res = "+1"
                                if lab_stats[cdata[-1]][-1] == "error":
                                    res = "-1"
                                res = "%s\n\n%s" % (res, o)
                                issue.create_comment(res)
                        if not dryRun:
                            last_commit_obj.create_status(
                                "success",
                                description="Finished",
                                target_url=status.target_url,
                                context=status.context,
                            )
                    logger.info("Lab Status %s", lab_stats)
                lab_state = "required"
                if lab_state not in lab_stats:
                    lab_state = "optional"
                if (lab_state in lab_stats) and ("pending" not in lab_stats[lab_state]):
                    signatures["tests"] = "approved"
                    if "error" in lab_stats[lab_state]:
                        signatures["tests"] = "rejected"
        elif not bot_status:
            if not dryRun:
                last_commit_obj.create_status(
                    "pending",
                    description="Waiting for authorized user to issue the test command.",
                    context=bot_status_name,
                )
            else:
                logger.debug(
                    "DryRun: Setting status Waiting for authorized user to issue the test command."
                )
    # Labels coming from signature.
    labels = []

    # Process "ignore tests failure"
    if override_tests_failure and signatures["tests"] == "rejected":
        signatures["tests"] = "approved"
        labels.append("tests-" + override_tests_failure)

    # automatically approve CATS_TO_APPROVE_ON_TEST on test-approved
    xcats = CATS_TO_APPROVE_ON_TEST + ["orp", "tests", "code-checks"]
    logger.info("XCats: %s", xcats)
    if (signatures.get("tests") == "approved") and [c for c in signatures if not c in xcats]:
        for cat in [c for c in CATS_TO_APPROVE_ON_TEST if (signatures.get(c) == "pending")]:
            signatures[cat] = "approved"
            logger.warning("Overriding/Approving signatures for %s due to tests-approved", cat)

    for cat in signing_categories:
        l = cat + "-pending"
        if cat in signatures:
            l = cat + "-" + signatures[cat]
        labels.append(l)

    if not issue.pull_request and len(signing_categories) == 0:
        labels.append("pending-assignment")
    if is_hold:
        labels.append("hold")

    if "backport" in extra_labels:
        if backport_pr_num != extra_labels["backport"][1]:
            try:
                bp_pr = repo.get_pull(int(extra_labels["backport"][1]))
                backport_pr_num = extra_labels["backport"][1]
                if bp_pr.merged:
                    extra_labels["backport"][0] = "backport-ok"
            except Exception as e:
                logger.error("Unknown PR %s\n%s", backport_pr_num, e)
                backport_pr_num = ""
                extra_labels.pop("backport")

            if already_seen:
                if dryRun:
                    logger.debug(
                        "Update PR seen message to include backport PR number %s", backport_pr_num
                    )
                else:
                    new_msg = ""
                    for l in ensure_ascii(already_seen.body).split("\n"):
                        if BACKPORT_STR in l:
                            continue
                        new_msg += l + "\n"
                    if backport_pr_num:
                        new_msg = "%s%s%s\n" % (new_msg, BACKPORT_STR, backport_pr_num)
                    already_seen.edit(body=new_msg)
        elif "backport-ok" in old_labels:
            extra_labels["backport"][0] = "backport-ok"

    # Add additional labels
    for lab in extra_testers:
        labels.append("allow-" + lab)
    for lab in extra_labels:
        if lab != "mtype":
            labels.append(extra_labels[lab][0])
        else:
            for slab in extra_labels[lab]:
                labels.append(slab)
    if comp_warnings:
        labels.append("compilation-warnings")

    if cms_repo and issue.pull_request and (not new_bot_tests):
        if comparison_done:
            labels.append("comparison-available")
        elif comparison_notrun:
            labels.append("comparison-notrun")
        else:
            labels.append("comparison-pending")

    if ("PULL_REQUESTS" in global_test_params) or cmssw_prs:
        need_external = True
    # Now updated the labels.
    xlabs = ["backport", "urgent", "backport-ok", "compilation-warnings"]
    for xtype in extra_labels:
        if xtype != "mtype":
            xlabs.append(extra_labels[xtype][0])
        else:
            for lab in extra_labels["mtype"]:
                xlabs.append(lab)

    missingApprovals = [
        x
        for x in labels
        if not x.endswith("-approved")
        and not x.startswith("orp")
        and not x.startswith("tests")
        and not x.startswith("pending-assignment")
        and not x.startswith("comparison")
        and not x.startswith("code-checks")
        and not x.startswith("allow-")
        and not x in xlabs
    ]

    logger.info("Missing Approvals: %s", missingApprovals)
    if not missingApprovals:
        logger.info("The pull request is complete.")
    if missingApprovals:
        labels.append("pending-signatures")
    elif not "pending-assignment" in labels:
        if not is_draft_pr:
            labels.append("fully-signed")
        else:
            labels.append("fully-signed-draft")
    if need_external:
        labels.append("requires-external")

    if (not bot_status) and issue.state != "open":
        labels = [l for l in labels if not l.startswith("tests-")]
        labels.extend(l for l in old_labels if l.startswith("tests-"))

    labels = set(labels)
    logger.info("New Labels: %s", sorted(labels))

    new_categories = set([])
    for nc_lab in pkg_categories:
        ncat = [nc_lab for oc_lab in old_labels if oc_lab.startswith(nc_lab + "-")]
        if ncat:
            continue
        new_categories.add(nc_lab)

    if new_assign_cats:
        tmp_gh_user_char = gh_user_char
        if notify_user(issue):
            gh_user_char = "@"
        new_l2s = [
            gh_user_char + name
            for name, l2_categories in list(CMSSW_L2.items())
            for signature in new_assign_cats
            if signature in l2_categories
        ]
        new_l2s = sorted(set(new_l2s), key=lambda s: s.lower())
        if not dryRun:
            issue.create_comment(
                "New categories assigned: "
                + ",".join(new_assign_cats)
                + "\n\n"
                + ",".join(new_l2s)
                + " you have been requested to review this Pull request/Issue and eventually sign? Thanks"
            )
        gh_user_char = tmp_gh_user_char

    # update blocker massge
    if new_blocker:
        if not dryRun:
            issue.create_comment(
                HOLD_MSG
                + blockers
                + "\nThey need to issue an `unhold` command to remove the `hold` state or L1 can `unhold` it for all"
            )
        logger.info("Blockers: %s", blockers)

    logger.debug("Changed Labels: added %s, removed %s", labels - old_labels, old_labels - labels)
    on_labels_changed(labels - old_labels, old_labels - labels)
    if old_labels == labels:
        logger.info("Labels unchanged.")
    elif not dryRunOrig:
        add_labels = True
        try:
            add_labels = repo_config.ADD_LABELS
        except:
            pass
        if add_labels and create_status:
            issue.edit(labels=list(labels))

    if not issue.pull_request:
        issueMessage = None
        if not already_seen:
            backport_msg = ""
            if backport_pr_num:
                backport_msg = "%s%s\n" % (BACKPORT_STR, backport_pr_num)
            l2s = ", ".join(gh_user_char + name for name in sorted(CMSSW_ISSUES_TRACKERS))
            issueMessage = format(
                "%(msgPrefix)s %(gh_user_char)s%(user)s.\n\n"
                "%(l2s)s can you please review it and eventually sign/assign?"
                " Thanks.\n\n"
                'cms-bot commands are listed <a href="http://cms-sw.github.io/cms-bot-cmssw-issues.html">here</a>\n%(backport_msg)s',
                msgPrefix=NEW_ISSUE_PREFIX,
                user=requestor,
                gh_user_char=gh_user_char,
                backport_msg=backport_msg,
                l2s=l2s,
            )
        elif ("fully-signed" in labels) and (not "fully-signed" in old_labels):
            issueMessage = "This issue is fully signed and ready to be closed."
        logger.debug("Issue: Post Message %s", issueMessage)
        write_bot_cache(bot_cache, technical_comments, issue, dryRunOrig)
        if issueMessage and not dryRun:
            issue.create_comment(issueMessage)
        return

    # get release managers
    SUPER_USERS = read_repo_file(repo_config, "super-users.yaml", [])
    releaseManagersList = ", ".join([gh_user_char + x for x in set(releaseManagers + SUPER_USERS)])

    if cmssw_prs:
        global_test_params["PULL_REQUESTS"] = cmssw_prs
    if extra_wfs:
        global_test_params["MATRIX_EXTRAS"] = extra_wfs
    if release_queue:
        global_test_params["RELEASE_FORMAT"] = release_queue
    if not "PULL_REQUESTS" in global_test_params:
        global_test_params["PULL_REQUESTS"] = "%s#%s" % (repository, prId)
    else:
        global_test_params["PULL_REQUESTS"] = "%s#%s %s" % (
            repository,
            prId,
            global_test_params["PULL_REQUESTS"],
        )
    if ignore_tests:
        if ignore_tests == "NONE":
            ignore_tests = ""
        global_test_params["IGNORE_BOT_TESTS"] = ignore_tests
    if enable_tests:
        if enable_tests == "NONE":
            enable_tests = ""
        global_test_params["ENABLE_BOT_TESTS"] = enable_tests
    if release_arch:
        global_test_params["ARCHITECTURE_FILTER"] = release_arch
    global_test_params["EXTRA_RELVALS_TESTS"] = " ".join(
        [t.upper().replace("-", "_") for t in EXTRA_RELVALS_TESTS]
    )

    logger.debug("All Parameters: %s", global_test_params)
    # For now, only trigger tests for cms-sw/cmssw and cms-sw/cmsdist
    if create_test_property:
        global_test_params["CONTEXT_PREFIX"] = cms_status_prefix
        if trigger_test:
            create_properties_file_tests(
                repository, prId, global_test_params, dryRun, abort=False, repo_config=repo_config
            )
            set_comment_emoji_cache(dryRun, bot_cache, test_comment, repository)
        elif abort_test and bot_status and (not bot_status.description.startswith("Aborted")):
            if not has_user_emoji(bot_cache, abort_test, repository, "+1", cmsbuild_user):
                create_properties_file_tests(
                    repository, prId, global_test_params, dryRun, abort=True
                )
                set_comment_emoji_cache(dryRun, bot_cache, abort_test, repository)
                if not dryRun:
                    last_commit_obj.create_status(
                        "pending",
                        description="Aborted, waiting for authorized user to issue the test command.",
                        target_url=abort_test.html_url,
                        context=bot_status_name,
                    )

    # Do not complain about tests
    requiresTestMessage = " after it passes the integration tests"
    if labels.intersection(set("tests-" + x for x in TEST_IGNORE_REASON)):
        requiresTestMessage = " (test failures were overridden)"
    elif "tests-approved" in labels:
        requiresTestMessage = " (tests are also fine)"
    elif "tests-rejected" in labels:
        requiresTestMessage = " (but tests are reportedly failing)"

    autoMergeMsg = ""
    if (
        ("fully-signed" in labels)
        and ("tests-approved" in labels)
        and ((not "orp" in signatures) or (signatures["orp"] == "approved"))
    ):
        autoMergeMsg = "This pull request will be automatically merged."
    else:
        if is_hold:
            autoMergeMsg = format(
                "This PR is put on hold by %(blockers)s. They have"
                " to `unhold` to remove the `hold` state or"
                " %(managers)s will have to `merge` it by"
                " hand.",
                blockers=blockers,
                managers=releaseManagersList,
            )
        elif "new-package-pending" in labels:
            autoMergeMsg = format(
                "This pull request requires a new package and "
                " will not be merged. %(managers)s",
                managers=releaseManagersList,
            )
        elif ("orp" in signatures) and (signatures["orp"] != "approved"):
            if not is_draft_pr:
                autoMergeMsg = format(
                    "This pull request will now be reviewed by the release team"
                    " before it's merged. %(managers)s (and backports should be raised in the release meeting by the corresponding L2)",
                    managers=releaseManagersList,
                )
            else:
                if ("fully-signed-draft" in labels) and (not "fully-signed-draft" in old_labels):
                    messageFullySignedDraft = f'@{pr.user.login} if this PR is ready to be reviewed by the release team, please remove the "Draft" status.'
                    if not dryRun:
                        issue.create_comment(messageFullySignedDraft)
                    else:
                        logger.debug("DRY-RUN: not posting comment %s", messageFullySignedDraft)

    devReleaseRelVal = ""
    if (pr.base.ref in RELEASE_BRANCH_PRODUCTION) and (pr.base.ref != "master"):
        devReleaseRelVal = (
            " and once validation in the development release cycle "
            + CMSSW_DEVEL_BRANCH
            + " is complete"
        )

    if ("fully-signed" in labels) and (not "fully-signed" in old_labels):
        messageFullySigned = format(
            "This pull request is fully signed and it will be"
            " integrated in one of the next %(branch)s IBs"
            "%(requiresTest)s"
            "%(devReleaseRelVal)s."
            " %(autoMerge)s",
            requiresTest=requiresTestMessage,
            autoMerge=autoMergeMsg,
            devReleaseRelVal=devReleaseRelVal,
            branch=pr.base.ref,
        )

        messageNotifyExternalPRs = ""
        if "PULL_REQUESTS" in global_test_params:
            unclosed_linked_prs = []
            linked_prs = global_test_params["PULL_REQUESTS"].split()
            extra_repos = {repository: repo}
            for linked_pr in linked_prs[1:]:
                linked_pr_repo, linked_pr_id = linked_pr.split("#")
                if not linked_pr_repo in extra_repos:
                    extra_repos[linked_pr_repo] = gh.get_repo(linked_pr_repo)
                r = extra_repos[linked_pr_repo]
                linked_pr_obj = r.get_issue(int(linked_pr_id))
                if linked_pr_obj.state != "closed":
                    unclosed_linked_prs.append(linked_pr)
                    comment_text = (
                        "**REMINDER** "
                        + releaseManagersList
                        + ": This PR was tested with "
                        + linked_prs[0]
                        + ", please check if they should be merged together"
                    )

                    if not dryRun:
                        linked_pr_obj.create_comment(comment_text)
                    else:
                        logger.debug("DRY-RUN: not posting comment %s", comment_text)

            messageNotifyExternalPRs = ", ".join(unclosed_linked_prs)

        if messageNotifyExternalPRs:
            messageFullySigned += (
                "\n**Notice** This PR was tested with additional Pull Request(s), please also merge them if necessary: "
                + messageNotifyExternalPRs
            )

        logger.debug("Fully signed message updated")
        if not dryRun:
            issue.create_comment(messageFullySigned)
        else:
            logger.debug("DRY-RUN: not posting comment %s", messageFullySigned)

    unsigned = [commit_sha for (commit_sha, v) in list(signatures.items()) if v == "pending"]
    missing_notifications = sorted(
        list(
            set(
                gh_user_char + name
                for name, l2_categories in list(CMSSW_L2.items())
                for signature in signing_categories
                if signature in l2_categories
                and signature in unsigned
                and signature not in ["orp"]
            )
        )
    )

    # Construct message for the watchers
    watchersMsg = ""
    if watchers:
        watchersMsg = format(
            "%(watchers)s this is something you requested to" " watch as well.\n",
            watchers=", ".join(sorted(watchers)),
        )
    # Construct message for the release managers.
    managers = ", ".join([gh_user_char + x for x in sorted(releaseManagers)])

    releaseManagersMsg = ""
    if releaseManagers:
        releaseManagersMsg = format(
            "%(managers)s you are the release manager for this.\n", managers=managers
        )

    # Add a Warning if the pull request was done against a patch branch
    if cmssw_repo:
        warning_msg = ""
        if "patchX" in pr.base.ref:
            logger.info("Must warn that this is a patch branch")
            base_release = pr.base.ref.replace("_patchX", "")
            base_release_branch = re.sub("[0-9]+$", "X", base_release)
            warning_msg = format(
                "Note that this branch is designed for requested bug "
                "fixes specific to the %(base_rel)s release.\nIf you "
                "wish to make a pull request for the %(base_branch)s "
                "release cycle, please use the %(base_branch)s branch instead\n",
                base_rel=base_release,
                base_branch=base_release_branch,
            )

        # We do not want to spam people for the old pull requests.
        pkg_msg = []
        for pkg in packages:
            if pkg in package_categories:
                pkg_msg.append("- %s (**%s**)" % (pkg, ", ".join(package_categories[pkg])))
            else:
                pkg_msg.append("- %s (**new**)" % pkg)
        messageNewPR = format(
            "%(msgPrefix)s %(gh_user_char)s%(user)s"
            " for %(branch)s.\n\n"
            "It involves the following packages:\n\n"
            "%(packages)s\n\n"
            "%(new_package_message)s\n"
            "%(l2s)s can you please review it and eventually sign?"
            " Thanks.\n"
            "%(watchers)s"
            "%(releaseManagers)s"
            "%(patch_branch_warning)s\n"
            'cms-bot commands are listed <a href="http://cms-sw.github.io/cms-bot-cmssw-cmds.html">here</a>\n',
            msgPrefix=NEW_PR_PREFIX,
            user=pr.user.login,
            gh_user_char=gh_user_char,
            branch=pr.base.ref,
            l2s=", ".join(missing_notifications),
            packages="\n".join(pkg_msg),
            new_package_message=new_package_message,
            watchers=watchersMsg,
            releaseManagers=releaseManagersMsg,
            patch_branch_warning=warning_msg,
        )

        messageUpdatedPR = format(
            "Pull request #%(pr)s was updated.",
            pr=pr.number,
        )

        if not is_draft_pr:
            messageUpdatedPR += format(
                " %(signers)s can you please check and sign again.\n",
                signers=", ".join(missing_notifications),
            )
    else:
        messageNewPR = format(
            "%(msgPrefix)s %(gh_user_char)s%(user)s"
            " for branch %(branch)s.\n\n"
            "%(l2s)s can you please review it and eventually sign?"
            " Thanks.\n"
            "%(watchers)s"
            "%(releaseManagers)s"
            'cms-bot commands are listed <a href="http://cms-sw.github.io/cms-bot-cmssw-cmds.html">here</a>\n',
            msgPrefix=NEW_PR_PREFIX,
            user=pr.user.login,
            gh_user_char=gh_user_char,
            branch=pr.base.ref,
            l2s=", ".join(missing_notifications),
            releaseManagers=releaseManagersMsg,
            watchers=watchersMsg,
        )

        messageUpdatedPR = format("Pull request #%(pr)s was updated.", pr=pr.number)

    # Finally decide whether or not we should close the pull request:
    messageBranchClosed = format(
        "This branch is closed for updates."
        " Closing this pull request.\n"
        " Please bring this up in the ORP"
        " meeting if really needed.\n"
    )

    commentMsg = ""
    logger.debug(
        "Status: already_seen=%s, pull_request_updated=%s", already_seen, pull_request_updated
    )
    if is_closed_branch(pr.base.ref) and (pr.state != "closed"):
        commentMsg = messageBranchClosed
    elif (already_seen or is_draft_pr) and pull_request_updated:
        commentMsg = messageUpdatedPR
    elif not already_seen and not is_draft_pr:
        commentMsg = messageNewPR
    elif new_categories:
        commentMsg = messageUpdatedPR
    elif not missingApprovals:
        logger.debug("Pull request is already fully signed. Not sending message.")
    else:
        logger.debug("Already notified L2 about %s", pr.number)
    if commentMsg and dryRun:
        logger.debug("The following comment will be made:")
        try:
            logger.debug(ensure_ascii(commentMsg))
        except:
            pass
    for pre_check in pre_checks + extra_pre_checks:
        if pre_check not in signatures:
            signatures[pre_check] = "pending"
        logger.debug(
            "PRE CHECK: pre_check=%s, signatures=%s, state=%s",
            pre_check,
            signatures[pre_check],
            pre_checks_state[pre_check],
        )

        if signatures[pre_check] != "pending":
            if pre_checks_state[pre_check] in ["pending", ""]:
                state = "success" if signatures[pre_check] == "approved" else "error"
                url = pre_checks_url[pre_check]
                logger.info(
                    "Setting status: pre_check=%s, state=%s, url=%s", pre_check, state, url
                )
                if not dryRunOrig:
                    last_commit_obj.create_status(
                        state,
                        target_url=url,
                        description="Check details",
                        context="%s/%s" % (cms_status_prefix, pre_check),
                    )
            continue
        if (not dryRunOrig) and (pre_checks_state[pre_check] == ""):
            params = {"PULL_REQUEST": "%s" % (prId), "CONTEXT_PREFIX": cms_status_prefix}
            if pre_check == "code-checks":
                params["CMSSW_TOOL_CONF"] = code_checks_tools
                params["APPLY_PATCH"] = str(code_check_apply_patch).lower()
            create_properties_file_tests(
                repository, prId, params, dryRunOrig, abort=False, req_type=pre_check
            )
            last_commit_obj.create_status(
                "pending",
                description="%s requested" % pre_check,
                context="%s/%s" % (cms_status_prefix, pre_check),
            )
        else:
            logger.debug("Dryrun: Setting pending status for %s", pre_check)

    if commentMsg and not dryRun:
        issue.create_comment(commentMsg)

    # Check if it needs to be automatically merged.
    if all(
        [
            "fully-signed" in labels,
            "tests-approved" in labels,
            "orp-approved" in labels,
            not "hold" in labels,
            not "new-package-pending" in labels,
        ]
    ):
        logger.info("This pull request can be automatically merged")
        mustMerge = True
    else:
        logger.warning("This pull request will not be automatically merged.")
    if mustMerge is True:
        logger.info("This pull request must be merged.")
        if not dryRun and (pr.state == "open"):
            pr.merge()

    state = get_status(bot_test_param_name, commit_statuses)
    if len(test_params_msg) > 140:
        test_params_msg = test_params_msg[:135] + "..."
    if ((not state) and (test_params_msg != "")) or (
        state and state.description != test_params_msg
    ):
        if test_params_msg == "":
            test_params_msg = "No special test parameter set."
        logger.info("Test params: %s", test_params_msg)
        url = ""
        if test_params_comment:
            if not dryRun:
                emoji = "-1" if "ERRORS: " in test_params_msg else "+1"
                state = "success" if emoji == "+1" else "error"
                last_commit_obj.create_status(
                    state,
                    description=test_params_msg,
                    target_url=test_params_comment.html_url,
                    context=bot_test_param_name,
                )
                set_comment_emoji_cache(
                    dryRun, bot_cache, test_params_comment, repository, emoji=emoji
                )
    write_bot_cache(bot_cache, technical_comments, issue, dryRunOrig)
    if ack_comment:
        state = get_status(bot_ack_name, commit_statuses)
        if (not state) or (state.target_url != ack_comment.html_url):
            desc = "Comment by %s at %s UTC processed." % (
                ensure_ascii(ack_comment.user.login),
                ack_comment.created_at,
            )
            logger.debug("Create bot/ack status: %s", desc)
            if not dryRun:
                last_commit_obj.create_status(
                    "success",
                    description=desc,
                    target_url=ack_comment.html_url,
                    context=bot_ack_name,
                )
