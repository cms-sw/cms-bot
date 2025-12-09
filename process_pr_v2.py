#!/usr/bin/env python3
"""
cms-bot: A GitHub bot for automating CI tests and PR reviews.

This bot is stateless except for a small cache stored in PR issue comments.
It handles code ownership, approval workflows, and merge automation.
"""

import base64
import zlib
import itertools
import json
import logging
import re
import sys
import types
import yaml
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from json import load as json_load
from os import getenv as os_getenv
from os.path import dirname, exists, join
from typing import Any, Dict, Generator, List, Optional, Set, Tuple, Union

import forward_ports_map
from _py2with3compatibility import run_cmd

from categories import (
    CMSSW_L2,
    CMSSW_ORP,
    TRIGGER_PR_TESTS,
    CMSSW_ISSUES_TRACKERS,
    PR_HOLD_MANAGERS,
    EXTERNAL_REPOS,
)
from categories import CMSSW_CATEGORIES

# Import CMSSW_LABELS for auto-labeling based on file patterns
try:
    from categories import CMSSW_LABELS
except ImportError:
    CMSSW_LABELS: Dict[str, List[Any]] = {}

# Import get_dpg_pog for DPG/POG label filtering
try:
    from categories import get_dpg_pog
except ImportError:

    def get_dpg_pog(*args) -> Dict[str, Any]:
        return {}


# Import external_to_package for mapping external repos to packages
try:
    from categories import external_to_package
except ImportError:

    def external_to_package(*args) -> str:
        return ""


from releases import RELEASE_BRANCH_MILESTONE, RELEASE_BRANCH_PRODUCTION, CMSSW_DEVEL_BRANCH

# Import release management functions
try:
    from releases import get_release_managers, is_closed_branch
except ImportError:

    def get_release_managers(*args) -> List[str]:
        return []

    def is_closed_branch(*args) -> bool:
        return False


from cms_static import (
    VALID_CMSDIST_BRANCHES,
    NEW_ISSUE_PREFIX,
    NEW_PR_PREFIX,
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

# Derived constants
CMSSW_REPO_NAME = join(GH_REPO_ORGANIZATION, GH_CMSSW_REPO)

# =============================================================================
# LOGGING SETUP
# =============================================================================


def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributeError` if the level name is already an attribute of the
    `logging` module or if the method name is already present

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
        return
    if hasattr(logging, methodName):
        return
    if hasattr(logging.getLoggerClass(), methodName):
        return

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(levelNum):
            self._log(levelNum, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


logger = logging.getLogger("cms-bot")


def setup_logging(loglevel):
    addLoggingLevel("TRACE", logging.DEBUG - 5)

    if isinstance(loglevel, int):
        numeric_level = loglevel
    else:
        numeric_level = getattr(logging, loglevel.upper(), None)
        if numeric_level is None:
            raise ValueError(f"Invalid log level: {loglevel}")

    global logger
    logger = logging.getLogger(__name__)
    if not len(logger.handlers):
        logger.setLevel(numeric_level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter("%(filename)s:%(lineno)d [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================


class ApprovalState(Enum):
    """Possible approval states for a file or category."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PRState(Enum):
    """Possible states for a Pull Request."""

    TESTS_PENDING = "tests-pending"
    SIGNATURES_PENDING = "signatures-pending"
    FULLY_SIGNED = "fully-signed"
    MERGED = "merged"


# Cache comment marker - identifies bot cache comments
CACHE_COMMENT_MARKER = CMSBOT_TECHNICAL_MSG + "<!--"
CACHE_COMMENT_END = "-->"

# Maximum size for cache data per comment chunk
# GitHub limit is 65535 chars, but cache is embedded in comment with markers,
# so we limit data portion to 55000 chars (matching old cms-bot behavior)
BOT_CACHE_CHUNK_SIZE = 55000

# Reaction types
REACTION_PLUS_ONE = "+1"
REACTION_MINUS_ONE = "-1"

# Commit and file count thresholds
TOO_MANY_COMMITS_WARN_THRESHOLD = 150  # Warning level
TOO_MANY_COMMITS_FAIL_THRESHOLD = 240  # Hard block level (no override possible)
TOO_MANY_FILES_WARN_THRESHOLD = 1500  # Warning level
TOO_MANY_FILES_FAIL_THRESHOLD = 3001  # Hard block level (no override possible)

# Bot command patterns that are reset on new commits
# (code-checks results, CI test results like +1/-1)
# These are only skipped when from bot comments before the latest commit
BOT_COMMANDS_RESET_ON_PUSH = [
    r"^[+-]code-checks$",
    r"^[+-]1$",
]

# Regex patterns for build/test command parameters
WF_PATTERN = r"(?:[a-z][a-z0-9_]+|[1-9][0-9]*(?:\.[0-9]+)?)"
CMSSW_QUEUE_PATTERN = "CMSSW_[0-9]+_[0-9]+_(X|[A-Z][A-Z0-9]+_X|[0-9]+(_[a-zA-Z0-9_]+)?)"
CMSSW_PACKAGE_PATTERN = "[A-Z][a-zA-Z0-9]+(?:/[a-zA-Z0-9]+|)"
ARCH_PATTERN = "[a-z0-9]+_[a-z0-9]+_[a-z0-9]+"
CMSSW_RELEASE_QUEUE_PATTERN = (
    f"(?:{CMSSW_QUEUE_PATTERN}|{ARCH_PATTERN}|{CMSSW_QUEUE_PATTERN}/{ARCH_PATTERN})"
)
RELVAL_OPTS = r"[-][a-zA-Z0-9_.,\s/'-]+"
JENKINS_NODES = r"[a-zA-Z0-9_|&\s()-]+"

CMS_PR_PATTERN = (
    "(?:#[1-9][0-9]*|(?:{cmsorgs})/+[a-zA-Z0-9_-]+#[1-9][0-9]*"
    "|https://+github.com/+(?:{cmsorgs})/+[a-zA-Z0-9_-]+/+pull/+[1-9][0-9]*)".format(
        cmsorgs="|".join(EXTERNAL_REPOS),
    )
)

RE_WF_LIST = re.compile(f"{WF_PATTERN}(,{WF_PATTERN})*")
RE_PR_LIST = re.compile(f"{CMS_PR_PATTERN}(,{CMS_PR_PATTERN})*")
RE_PKG_LIST = re.compile(f"{CMSSW_PACKAGE_PATTERN}(,{CMSSW_PACKAGE_PATTERN})*")
RE_QUEUE = re.compile(CMSSW_RELEASE_QUEUE_PATTERN)
TEST_VERBS = ("build", "test")


# GPU flavors (loaded from files)
def _load_gpu_flavors() -> List[str]:
    """Load GPU flavors from configuration files."""
    gpus = []
    base_dir = dirname(__file__)
    for filename in ("gpu_flavors.txt", "gpu_flavors_ondemand.txt"):
        filepath = join(base_dir, filename)
        try:
            with open(filepath, "r") as f:
                gpus.extend(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            pass
    return gpus


ALL_GPUS = _load_gpu_flavors()
ALL_GPU_BRANDS = sorted(set(gpu.split("_", 1)[0] for gpu in ALL_GPUS))

# Test-related patterns
EXTRA_RELVALS_TESTS = ["threading", "gpu", "high_stats", "nano"]
EXTRA_RELVALS_TESTS_OPTS = "_" + "|_".join(EXTRA_RELVALS_TESTS)
EXTRA_TESTS = (
    "|".join(EXTRA_RELVALS_TESTS)
    + "|hlt_p2_integration|hlt_p2_timing|profiling|none|multi_microarchs"
)
SKIP_TESTS = "|".join(["static", "header"])
ENABLE_TEST_PTRN = "enable(_tests?)?"

# Multiline comment parameter mapping for 'test parameters:' command
# Format: {key_pattern: [value_pattern, param_name, preserve_spaces?]}
MULTILINE_COMMENTS_MAP: Dict[str, List[Any]] = {
    f"(workflow|relval)s?({EXTRA_RELVALS_TESTS_OPTS})?": [
        rf"({WF_PATTERN})(,({WF_PATTERN}))*",
        "MATRIX_EXTRAS",
    ],
    "(workflow|relval)s?_profiling": [
        rf"({WF_PATTERN})(,({WF_PATTERN}))*",
        "PROFILING_WORKFLOWS",
    ],
    "pull_requests?": [
        f"{CMS_PR_PATTERN}(,{CMS_PR_PATTERN})*",
        "PULL_REQUESTS",
    ],
    "full_cmssw|full": ["true|false", "BUILD_FULL_CMSSW"],
    "disable_poison": ["true|false", "DISABLE_POISON"],
    "use_ib_tag": ["true|false", "USE_IB_TAG"],
    "baseline": ["self|default", "USE_BASELINE"],
    "set_env": [r"[A-Z][A-Z0-9_]+(,[A-Z][A-Z0-9_]+)*", "CMSBOT_SET_ENV"],
    f"skip_tests?": [rf"({SKIP_TESTS})(,({SKIP_TESTS}))*", "SKIP_TESTS"],
    "dry_run": ["true|false", "DRY_RUN"],
    "jenkins_(slave|node)": [JENKINS_NODES, "RUN_ON_SLAVE"],
    "(arch(itectures?)?|release|release/arch)": [CMSSW_RELEASE_QUEUE_PATTERN, "RELEASE_FORMAT"],
    ENABLE_TEST_PTRN: [
        rf"({EXTRA_TESTS})(,({EXTRA_TESTS}))*",
        "ENABLE_BOT_TESTS",
    ],
    "ignore_tests?": ["build-warnings|clang-warnings", "IGNORE_BOT_TESTS"],
    "container": [
        r"[a-zA-Z][a-zA-Z0-9_-]+/[a-zA-Z][a-zA-Z0-9_-]+(:[a-zA-Z0-9_-]+)?",
        "DOCKER_IMGAGE",
    ],
    "cms-addpkg|addpkg": [
        f"{CMSSW_PACKAGE_PATTERN}(,({CMSSW_PACKAGE_PATTERN}))*",
        "EXTRA_CMSSW_PACKAGES",
    ],
    "build_verbose": ["true|false", "BUILD_VERBOSE"],
    f"(workflow|relval)s?_opt(ion)?s?({EXTRA_RELVALS_TESTS_OPTS}|_input)?": [
        RELVAL_OPTS,
        "EXTRA_MATRIX_ARGS",
        True,
    ],
    f"(workflow|relval)s?_command_opt(ion)?s?({EXTRA_RELVALS_TESTS_OPTS}|_input)?": [
        RELVAL_OPTS,
        "EXTRA_MATRIX_COMMAND_ARGS",
        True,
    ],
    "gpu(_flavor|_type)?s?": [
        f"({'|'.join(itertools.chain(ALL_GPUS, ALL_GPU_BRANDS))})(,({'|'.join(itertools.chain(ALL_GPUS, ALL_GPU_BRANDS))}))*",
        "SELECTED_GPU_TYPES",
    ],
}

# Regex patterns for PR description flags (compiled from cms_static constants)
RE_CMS_BOT_IGNORE = re.compile(CMSBOT_IGNORE_MSG, re.IGNORECASE)
RE_NOTIFY_NO_AT = re.compile(CMSBOT_NO_NOTIFY_MSG, re.IGNORECASE)

# Global L2 data cache
_L2_DATA: Dict[str, List[Dict[str, Any]]] = {}


# =============================================================================
# HELPER FUNCTIONS FOR TEST PARAMETERS
# =============================================================================


def get_prs_list_from_string(pr_string: str, repo_string: str = "") -> List[str]:
    """
    Parse a comma-separated PR string into a list of normalized PR references.

    Args:
        pr_string: Comma-separated PR references
        repo_string: Default repository for bare PR numbers

    Returns:
        List of normalized PR references (org/repo#number format)
    """
    prs = []
    for pr in pr_string.split(","):
        pr = pr.strip()
        if not pr:
            continue
        # Handle full GitHub URLs
        if "/github.com/" in pr:
            pr = pr.split("/github.com/", 1)[-1]
            pr = pr.replace("/pull/", "#").strip("/")
        # Normalize double slashes
        while "//" in pr:
            pr = pr.replace("//", "/")
        # Add repo prefix for bare PR numbers
        if pr.startswith("#"):
            pr = repo_string + pr
        prs.append(pr)
    return prs


def check_ignore_bot_tests(value: str, *args) -> Tuple[str, Optional[str]]:
    """Normalize IGNORE_BOT_TESTS value."""
    return value.upper().replace(" ", ""), None


def check_enable_bot_tests(value: str, *args) -> Tuple[str, Optional[str]]:
    """Normalize ENABLE_BOT_TESTS value, handling 'none' specially."""
    tests = value.upper().replace(" ", "")
    if "NONE" in tests:
        tests = "NONE"
    return tests, None


def check_extra_matrix_args(
    value: str, repo, params: Dict[str, str], key: str, param: str, *args
) -> Tuple[str, Optional[str]]:
    """Handle EXTRA_MATRIX_ARGS with suffix based on key."""
    key_parts = key.split("_")
    if key_parts[-1] in ["input"] + EXTRA_RELVALS_TESTS:
        param = f"{param}_{key_parts[-1].upper().replace('-', '_')}"
    return value, param


def check_extra_matrix_command_args(
    value: str, repo, params: Dict[str, str], key: str, param: str, *args
) -> Tuple[str, Optional[str]]:
    """Handle EXTRA_MATRIX_COMMAND_ARGS with suffix based on key."""
    # Same logic as check_extra_matrix_args
    return check_extra_matrix_args(value, repo, params, key, param, *args)


def check_matrix_extras(
    value: str, repo, params: Dict[str, str], key: str, param: str, *args
) -> Tuple[str, Optional[str]]:
    """Handle MATRIX_EXTRAS with suffix and sort workflows."""
    key_parts = key.split("_")
    if key_parts[-1] in EXTRA_RELVALS_TESTS:
        param = f"{param}_{key_parts[-1].upper().replace('-', '_')}"
    # Sort workflows
    value = ",".join(sorted(value.split(",")))
    return value, param


def check_pull_requests(value: str, repo, *args) -> Tuple[str, Optional[str]]:
    """Normalize PULL_REQUESTS value."""
    repo_string = repo.full_name if hasattr(repo, "full_name") else str(repo)
    return " ".join(get_prs_list_from_string(value, repo_string)), None


def check_release_format(
    value: str, repo, params: Dict[str, str], *args
) -> Tuple[str, Optional[str]]:
    """Handle RELEASE_FORMAT, extracting architecture if present."""
    release_queue = value
    arch = ""
    if "/" in release_queue:
        release_queue, arch = release_queue.split("/", 1)
    elif re.fullmatch(ARCH_PATTERN, release_queue):
        arch = release_queue
        release_queue = ""
    params["ARCHITECTURE_FILTER"] = arch
    return release_queue, None


# =============================================================================
# L2 DATA MANAGEMENT
# =============================================================================


def read_repo_file(
    repo_config: types.ModuleType,
    repo_file: str,
    default: Any = None,
    is_yaml: bool = True,
) -> Any:
    """
    Read a configuration file from the repository config directory.

    Args:
        repo_config: Repository configuration module
        repo_file: Name of the file to read
        default: Default value if file doesn't exist
        is_yaml: If True, parse as YAML; otherwise parse as JSON

    Returns:
        Parsed file contents or default value
    """
    file_path = join(repo_config.CONFIG_DIR, repo_file)
    contents = default

    if exists(file_path):
        with open(file_path, "r") as f:
            if is_yaml:
                contents = yaml.safe_load(f)
            else:
                contents = json_load(f)
        if not contents:
            contents = default

    return contents


def init_l2_data(
    repo_config: types.ModuleType, cms_repo: bool = True
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Initialize L2 category membership data.

    Loads L2 membership information from configuration files. For CMS repos,
    reads from l2.json in the config directory. For other repos, uses the
    static CMSSW_L2 mapping.

    Args:
        repo_config: Repository configuration module
        cms_repo: True if this is a CMS repository

    Returns:
        Dict mapping username to list of membership periods
        Each period has: start_date, category, and optionally end_date
    """
    global _L2_DATA

    if cms_repo:
        # Load default L2 data from cmssw_l2/l2.json
        default_l2_path = join(dirname(__file__), "cmssw_l2", "l2.json")
        default_l2_data: Dict[str, List[Dict[str, Any]]] = {}

        if exists(default_l2_path):
            with open(default_l2_path, "r") as f:
                default_l2_data = json_load(f)

        # Read repo-specific l2.json, falling back to default
        l2_data = read_repo_file(repo_config, "l2.json", default_l2_data, is_yaml=False)

        # For users in CMSSW_L2, ensure their latest period has no end_date
        for user in CMSSW_L2:
            if user in l2_data and l2_data[user]:
                if "end_date" in l2_data[user][-1]:
                    del l2_data[user][-1]["end_date"]
    else:
        # For non-CMS repos, use static CMSSW_L2 mapping
        l2_data = {}
        for user, category in CMSSW_L2.items():
            l2_data[user] = [{"start_date": 0, "category": category}]

    _L2_DATA = l2_data
    return l2_data


def get_watchers(
    context: "PRContext",
    changed_files: List[str],
    timestamp: datetime,
) -> Set[str]:
    """
    Get watchers for the PR based on changed files and categories.

    Watchers are users who want to be notified when certain files or
    categories are modified, but don't have signing permission.

    Args:
        context: PR processing context
        changed_files: List of files changed in the PR
        timestamp: Timestamp for lookups

    Returns:
        Set of usernames who should be notified
    """
    watchers: Set[str] = set()
    author = context.issue.user.login if context.issue else ""

    # Load file watchers from watchers.yaml
    file_watchers = read_repo_file(context.repo_config, "watchers.yaml", {})

    # Find watchers based on changed files
    for chg_file in changed_files:
        for user, watched_regexps in file_watchers.items():
            if user == author:
                continue
            for regexp in watched_regexps:
                if re.match(f"^{regexp}.*", chg_file):
                    watchers.add(user)
                    break

    # Load category watchers from category-watchers.yaml
    cat_watchers = read_repo_file(context.repo_config, "category-watchers.yaml", {})

    for user, cats in cat_watchers.items():
        if user == author:
            continue
        for cat in cats:
            if cat in context.signing_categories or cat in context.pending_labels:
                logger.debug(f"Added {user} to watch due to category {cat}")
                watchers.add(user)
                break

    # Expand watching groups
    watching_groups = read_repo_file(context.repo_config, "groups.yaml", {})
    expanded_watchers: Set[str] = set()

    for watcher in watchers:
        if watcher in watching_groups:
            # This is a group, expand it
            expanded_watchers.update(watching_groups[watcher])
        else:
            expanded_watchers.add(watcher)

    # Remove PR author from watchers
    expanded_watchers.discard(author)

    logger.info(f"Watchers: {', '.join(sorted(expanded_watchers))}")
    return expanded_watchers


# =============================================================================
# LABEL MANAGEMENT
# =============================================================================

# Compiled label patterns (populated by initialize_labels)
_LABEL_PATTERNS: Dict[str, List[re.Pattern]] = {}


def initialize_labels(repo_config: types.ModuleType) -> Dict[str, List[re.Pattern]]:
    """
    Initialize and compile label patterns for auto-labeling.

    Labels in CMSSW_LABELS map label names to file path patterns.
    This function:
    1. Optionally filters labels based on DPG/POG membership
    2. Compiles string patterns to regex objects

    Args:
        repo_config: Repository configuration module

    Returns:
        Dict mapping label names to lists of compiled regex patterns
    """
    global _LABEL_PATTERNS

    if _LABEL_PATTERNS:
        return _LABEL_PATTERNS

    # Check if DPG/POG filtering is enabled
    check_dpg_pog = getattr(repo_config, "CHECK_DPG_POG", False)
    dpg_pog = get_dpg_pog() if check_dpg_pog else {}

    compiled_labels: Dict[str, List[re.Pattern]] = {}

    for label, patterns in CMSSW_LABELS.items():
        # Filter out labels not in DPG/POG or TYPE_COMMANDS if checking is enabled
        if check_dpg_pog and label not in dpg_pog and label not in TYPE_COMMANDS:
            continue

        # Compile patterns
        compiled_patterns = []
        for pattern in patterns:
            if isinstance(pattern, str):
                compiled_patterns.append(re.compile(f"^({pattern}).*$"))
            elif isinstance(pattern, re.Pattern):
                compiled_patterns.append(pattern)
            # Skip invalid pattern types

        compiled_labels[label] = compiled_patterns

    _LABEL_PATTERNS = compiled_labels
    return compiled_labels


def get_labels_for_file(filename: str) -> List[str]:
    """
    Get labels that should be applied based on a filename.

    Args:
        filename: Path to the file

    Returns:
        List of label names that match the file
    """
    matching_labels = []

    for label, patterns in _LABEL_PATTERNS.items():
        for pattern in patterns:
            if pattern.match(filename):
                matching_labels.append(label)
                break  # Only add each label once per file

    return matching_labels


def get_labels_for_pr(context: "PRContext") -> Set[str]:
    """
    Get all labels that should be applied to a PR based on its files.

    Args:
        context: PR processing context

    Returns:
        Set of label names to apply
    """
    labels: Set[str] = set()
    current_files = context.cache.current_file_versions

    if not current_files:
        return labels

    for fv_key in current_files:
        if fv_key in context.cache.file_versions:
            fv = context.cache.file_versions[fv_key]
            labels.update(get_labels_for_file(fv.filename))

    return labels


def add_nonblocking_labels(changed_files: List[str], pending_labels: Set[str]) -> None:
    """
    Add non-blocking labels based on changed files.

    Matches changed files against CMSSW_LABELS patterns and adds matching
    labels to the pending_labels set.

    Args:
        changed_files: List of changed file paths
        pending_labels: Set to populate with labels (modified in place)
    """
    for pkg_file in changed_files:
        for label, patterns in _LABEL_PATTERNS.items():
            for regex in patterns:
                if regex.match(pkg_file):
                    pending_labels.add(label)
                    logger.debug(f"Non-blocking label: {label} for {pkg_file}")
                    break


# =============================================================================
# MILESTONE MANAGEMENT
# =============================================================================


def update_milestone(repo, issue, pr, dry_run: bool = False) -> None:
    """
    Update PR milestone based on target branch.

    Sets the milestone according to RELEASE_BRANCH_MILESTONE mapping.

    Args:
        repo: Repository object
        issue: Issue object
        pr: Pull request object
        dry_run: If True, don't make changes
    """
    milestone_id = RELEASE_BRANCH_MILESTONE.get(pr.base.label.split(":")[1], None)

    if not milestone_id:
        logger.warning("Unable to find a milestone for the given branch")
        return

    if pr.state != "open":
        logger.debug("PR not open, not setting/checking milestone")
        return

    if issue.milestone and issue.milestone.number == milestone_id:
        return

    milestone = repo.get_milestone(milestone_id)
    logger.info(f"Setting milestone to {milestone.title}")

    if dry_run:
        return

    issue.edit(milestone=milestone)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class FileVersion:
    """
    Tracks a specific version of a file (filename + blob_sha).

    Attributes:
        filename: Path to the file
        blob_sha: SHA of the file blob
        timestamp: When this version was first seen
        categories: L2 categories that own this file
    """

    filename: str
    blob_sha: str
    timestamp: str  # ISO format timestamp
    categories: List[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        """Return the unique key for this file version."""
        return f"{self.filename}::{self.blob_sha}"


@dataclass
class CommentInfo:
    """
    Cached information about a processed comment.

    Attributes:
        timestamp: When the comment was created (ISO format)
        first_line: First non-blank line of comment (for command detection)
        ctype: Command type detected (e.g., '+1', '-1', 'hold', 'test')
        categories: Categories affected by this command
        signed_files: File version keys (filename::sha) at time of signing
        user: Username who made the comment
        locked: If True, comment won't be re-processed even if edited
    """

    timestamp: str
    first_line: str
    ctype: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    signed_files: List[str] = field(default_factory=list)
    user: Optional[str] = None
    locked: bool = False


@dataclass
class Hold:
    """
    Represents a hold placed on a PR.

    Attributes:
        category: L2 category that placed the hold
        user: Username who placed the hold
        comment_id: ID of the comment containing the hold command
    """

    category: str
    user: str
    comment_id: int


@dataclass
class BotCache:
    """
    Cache stored in PR comments to avoid repeated API calls.

    Structure matches the JSON format:
    {
        "emoji": { "<comment_id>": "<reaction>" },  # Bot's reactions (source of truth)
        "fv": { "<filename>::<sha>": { "ts": ..., "cats": [...] } },  # File versions
        "comments": { "<comment_id>": { "ts": ..., "first_line": ..., ... } }  # Processed comments
    }
    """

    # Bot's reactions on comments (comment_id -> reaction)
    emoji: Dict[str, str] = field(default_factory=dict)

    # File versions (filename::sha -> FileVersion info)
    file_versions: Dict[str, FileVersion] = field(default_factory=dict)

    # Processed comments (comment_id -> CommentInfo)
    comments: Dict[str, CommentInfo] = field(default_factory=dict)

    # Runtime state: current file version keys (filename::sha) for this PR
    current_file_versions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize cache to dictionary matching the JSON format."""
        return {
            "emoji": self.emoji.copy(),
            "fv": {
                key: {
                    "ts": fv.timestamp,
                    "cats": fv.categories,
                }
                for key, fv in self.file_versions.items()
            },
            "comments": {
                cid: {
                    "ts": ci.timestamp,
                    "first_line": ci.first_line,
                    **({"ctype": ci.ctype} if ci.ctype else {}),
                    **({"cats": ci.categories} if ci.categories else {}),
                    **({"signed_files": ci.signed_files} if ci.signed_files else {}),
                    **({"user": ci.user} if ci.user else {}),
                    **({"locked": ci.locked} if ci.locked else {}),
                }
                for cid, ci in self.comments.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotCache":
        """Deserialize cache from dictionary."""
        cache = cls()

        # Load emoji (reactions)
        cache.emoji = {str(k): v for k, v in data.get("emoji", {}).items()}

        # Load file versions
        for key, fv_data in data.get("fv", {}).items():
            parts = key.split("::")
            if len(parts) == 2:
                filename, blob_sha = parts
                cache.file_versions[key] = FileVersion(
                    filename=filename,
                    blob_sha=blob_sha,
                    timestamp=fv_data.get("ts", ""),
                    categories=fv_data.get("cats", []),
                )

        # Load comments
        for cid, ci_data in data.get("comments", {}).items():
            cache.comments[str(cid)] = CommentInfo(
                timestamp=ci_data.get("ts", ""),
                first_line=ci_data.get("first_line", ""),
                ctype=ci_data.get("ctype"),
                categories=ci_data.get("cats", []),
                signed_files=ci_data.get("signed_files", []),
                user=ci_data.get("user"),
                locked=ci_data.get("locked", False),
            )

        return cache

    def get_cached_reaction(self, comment_id: int) -> Optional[str]:
        """Get the cached reaction for a comment."""
        return self.emoji.get(str(comment_id))

    def set_reaction(self, comment_id: int, reaction: str) -> None:
        """Set the reaction for a comment in cache."""
        self.emoji[str(comment_id)] = reaction


class TestCmdParseError(ValueError):
    """Error raised when parsing build/test command fails."""

    pass


@dataclass
class TestCmdResult:
    """Result of parsing a build/test command."""

    verb: str  # 'build' or 'test'
    workflows: List[str] = field(default_factory=list)
    prs: List[str] = field(default_factory=list)
    queue: str = ""
    using: bool = False
    full: str = ""
    addpkg: List[str] = field(default_factory=list)


@dataclass
class TestCmdParam:
    """Definition of a parameter for build/test command parsing."""

    keyword: Union[str, re.Pattern]
    field_name: str
    rx: Union[str, re.Pattern, None] = None
    split_by: Optional[str] = ","
    prev_keyword: Union[str, re.Pattern, None] = None

    def __post_init__(self):
        if isinstance(self.keyword, str):
            self.keyword = re.compile(self.keyword, re.IGNORECASE)
        if isinstance(self.rx, str):
            self.rx = re.compile(self.rx, re.IGNORECASE)
        if isinstance(self.prev_keyword, str):
            self.prev_keyword = re.compile(self.prev_keyword, re.IGNORECASE)


@dataclass
class TestRequest:
    """A request to run tests/build."""

    verb: str  # 'build' or 'test'
    workflows: str = ""  # Comma-separated workflow list
    prs: List[str] = field(default_factory=list)  # Additional PRs to include
    queue: str = ""  # Target queue
    build_full: bool = False  # Build full CMSSW
    extra_packages: str = ""  # Extra packages to add
    triggered_by: str = ""  # Username who triggered
    comment_id: int = 0  # Comment that triggered this

    @property
    def test_key(self) -> str:
        """
        Generate a unique key for this test configuration.

        Used to deduplicate test requests - only one test per unique
        combination of parameters is triggered.
        """
        # Sort PRs and workflows for consistent keys
        sorted_prs = ",".join(sorted(self.prs)) if self.prs else ""
        sorted_workflows = ",".join(sorted(self.workflows.split(","))) if self.workflows else ""
        return f"{self.verb}|{sorted_workflows}|{sorted_prs}|{self.queue}|{self.build_full}|{self.extra_packages}"


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================


def compress_cache(data: str) -> str:
    """Compress cache data using zlib + base64."""
    compressed = zlib.compress(data.encode("utf-8"))
    return base64.b64encode(compressed).decode("ascii")


def decompress_cache(data: str) -> str:
    """Decompress cache data from zlib + base64."""
    compressed = base64.b64decode(data.encode("ascii"))
    return zlib.decompress(compressed).decode("utf-8")


def load_cache_from_comments(comments: List[Any]) -> BotCache:
    """
    Load bot cache from PR issue comments.

    The cache is stored in comments with format:
    '{CMSBOT_TECHNICAL_MSG}<!-- {JSON or compressed data} -->'

    Multiple comments may be used if data is large.

    Args:
        comments: List of comment objects from the issue/PR
    """
    cache_parts = []

    for comment in comments:
        body = comment.body or ""
        if body.startswith(CACHE_COMMENT_MARKER):
            # Extract the data between markers
            start = len(CACHE_COMMENT_MARKER)
            end = body.rfind(CACHE_COMMENT_END)
            if end > start:
                cache_parts.append((comment.id, body[start:end].strip()))

    if not cache_parts:
        logger.debug("No cache found in comments, starting fresh")
        return BotCache()

    # Sort by comment ID to ensure correct order
    cache_parts.sort(key=lambda x: x[0])

    # Combine all parts
    combined_data = "".join(part for _, part in cache_parts)

    try:
        # Try to parse as JSON first
        try:
            data = json.loads(combined_data)
        except json.JSONDecodeError:
            # Try decompressing
            decompressed = decompress_cache(combined_data)
            data = json.loads(decompressed)

        logger.debug("Successfully loaded cache from comments")
        return BotCache.from_dict(data)

    except Exception as e:
        logger.warning(f"Failed to load cache: {e}, starting fresh")
        return BotCache()


def save_cache_to_comments(
    issue, comments: List[Any], cache: BotCache, dry_run: bool = False
) -> None:
    """
    Save bot cache to PR issue comments.

    Creates or updates cache comments. Will compress if > chunk size, then split if needed.
    Follows same logic as old cms-bot: compress entire cache first, then chunk.

    Args:
        issue: The issue/PR object (used for creating new comments)
        comments: List of existing comment objects
        cache: The cache to save
        dry_run: If True, don't actually save
    """
    # Serialize with compact separators and sorted keys (like old code)
    data = json.dumps(cache.to_dict(), separators=(",", ":"), sort_keys=True)

    # Compress if larger than chunk size (like old dumps_maybe_compress)
    if len(data) > BOT_CACHE_CHUNK_SIZE:
        data = compress_cache(data)

    # Split into chunks if still too large
    chunks = []
    while data:
        chunk, data = data[:BOT_CACHE_CHUNK_SIZE], data[BOT_CACHE_CHUNK_SIZE:]
        chunks.append(chunk)

    # Find existing cache comments
    existing_cache_comments = []
    for comment in comments:
        body = comment.body or ""
        if body.startswith(CACHE_COMMENT_MARKER):
            existing_cache_comments.append(comment)

    if dry_run:
        logger.info(f"[DRY RUN] Would save cache ({len(chunks)} chunk(s))")
        return

    # Update or create comments
    for i, chunk in enumerate(chunks):
        comment_body = f"{CACHE_COMMENT_MARKER} {chunk} {CACHE_COMMENT_END}"

        if i < len(existing_cache_comments):
            # Check if content actually changed
            old_body = existing_cache_comments[i].body or ""
            if old_body == comment_body:
                logger.debug(f"Cache comment {i + 1}/{len(chunks)} unchanged, skipping")
                continue
            # Update existing comment
            existing_cache_comments[i].edit(comment_body)
            logger.debug(f"Updated cache comment {i + 1}/{len(chunks)}")
        else:
            # Create new comment
            issue.create_comment(comment_body)
            logger.debug(f"Created cache comment {i + 1}/{len(chunks)}")

    # Delete extra old comments if new cache is smaller
    for i, comment in enumerate(existing_cache_comments[len(chunks) :], start=len(chunks)):
        logger.debug(
            f"Deleting extra cache comment {i + 1 - len(chunks)}/{len(existing_cache_comments) - len(chunks)}"
        )
        comment.delete()


# =============================================================================
# CODE OWNERSHIP FUNCTIONS (Stubs - to be provided externally)
# =============================================================================


def file_to_package(repo_config: types.ModuleType, filename: str) -> str:
    """
    Convert a file path to its package name.

    Uses repo_config.file2Package if available, otherwise extracts
    the first two path components (e.g., "Subsystem/Package").

    Args:
        repo_config: Repository configuration module
        filename: Path to the file

    Returns:
        Package name
    """
    try:
        return repo_config.file2Package(filename)
    except (AttributeError, Exception):
        # Default: extract first two path components
        parts = filename.split("/")
        if len(parts) >= 2:
            return "/".join(parts[0:2])
        return filename


def get_package_categories(package: str) -> List[str]:
    """
    Get L2 categories responsible for a package.

    Uses CMSSW_CATEGORIES from categories module.

    Args:
        package: Package name (e.g., "RecoTracker/PixelSeeding")

    Returns:
        List of category names responsible for this package
    """
    # CMSSW_CATEGORIES maps category -> list of packages
    # We need to invert this to find categories for a package
    categories = []
    for category, packages in CMSSW_CATEGORIES.items():
        if package in packages:
            categories.append(category)

    return categories


def get_file_l2_categories(
    repo_config: types.ModuleType, filename: str, commit_timestamp: datetime
) -> List[str]:
    """
    Determine L2 categories for a file based on path and timestamp.

    For CMSSW-style repos: file → package → categories (two-stage)
    For other repos: Returns empty list (relies on manual 'assign' command)

    The repo is considered CMSSW-style if it has a file2Package method
    or if CMSSW_CATEGORIES contains mappings.

    Args:
        repo_config: Repository configuration module
        filename: Path to the file
        commit_timestamp: Timestamp of the commit

    Returns:
        List of L2 category names that own this file (empty if manual assignment required)
    """
    # Check if this repo uses automatic category assignment
    has_file2package = hasattr(repo_config, "file2Package")
    has_category_mappings = bool(CMSSW_CATEGORIES)

    if not has_file2package and not has_category_mappings:
        # This repo relies on manual assignment via 'assign' command
        return []

    # Two-stage process: file → package → categories
    package = file_to_package(repo_config, filename)
    categories = get_package_categories(package)

    return categories


def get_user_l2_categories(
    repo_config: types.ModuleType, username: str, timestamp: datetime
) -> List[str]:
    """
    Determine which L2 categories a user belongs to at a given time.

    Uses the global L2 data loaded by init_l2_data().

    Args:
        repo_config: Repository configuration module
        username: GitHub username
        timestamp: Point in time to check membership

    Returns:
        List of L2 category names the user belongs to
    """
    if not _L2_DATA:
        # Fallback to static CMSSW_L2 if L2 data not initialized
        cat = CMSSW_L2.get(username)
        if cat is None:
            return []
        # Handle case where cat might be a list or string
        if isinstance(cat, list):
            return cat
        return [cat]

    if username not in _L2_DATA:
        return []

    # Find categories active at the given timestamp
    ts_epoch = timestamp.timestamp() if isinstance(timestamp, datetime) else timestamp

    for period in _L2_DATA[username]:
        start_date = period.get("start_date", 0)
        end_date = period.get("end_date")

        # Check if timestamp falls within this period
        if ts_epoch < start_date:
            return []

        if end_date is None or ts_epoch < end_date:
            cat = period.get("category", [])
            # Ensure we always return List[str], not List[List[str]]
            if isinstance(cat, str):
                return [cat]
            if isinstance(cat, list):
                # Flatten if nested
                result = []
                for c in cat:
                    if isinstance(c, list):
                        result.extend(c)
                    else:
                        result.append(c)
                return result
            return []

    return []


def get_category_l2s(
    repo_config: types.ModuleType, category: str, timestamp: datetime
) -> List[str]:
    """
    Get the L2 signers for a specific category.

    Args:
        repo_config: Repository configuration module
        category: Category name
        timestamp: Timestamp for time-based L2 lookup

    Returns:
        List of usernames who are L2 for this category
    """
    l2s = []
    timestamp_epoch = int(timestamp.timestamp())

    # Check CMSSW_L2 mapping
    for username, cat_or_periods in CMSSW_L2.items():
        if isinstance(cat_or_periods, str):
            if cat_or_periods == category:
                l2s.append(username)
        elif isinstance(cat_or_periods, list):
            # Check for time-based periods
            for item in cat_or_periods:
                if isinstance(item, dict):
                    start = item.get("start", 0)
                    end = item.get("end", float("inf"))
                    if start <= timestamp_epoch <= end:
                        cat = item.get("category", [])
                        if isinstance(cat, str) and cat == category:
                            l2s.append(username)
                        elif isinstance(cat, list) and category in cat:
                            l2s.append(username)
                        break
                elif item == category:
                    l2s.append(username)
                    break

    return l2s


def get_package_category(repo_config: types.ModuleType, package: str) -> Optional[str]:
    """
    Map a package name to its primary category.

    First checks repo_config.PACKAGE_CATEGORIES for explicit mapping,
    then falls back to CMSSW_CATEGORIES lookup.

    Args:
        repo_config: Repository configuration module
        package: Package name

    Returns:
        Category name or None if not found
    """
    # First check repo-specific mapping
    package_map = getattr(repo_config, "PACKAGE_CATEGORIES", {})
    if package in package_map:
        return package_map.get(package)

    # Fallback to CMSSW_CATEGORIES
    categories = get_package_categories(package)
    return categories[0] if categories else None


@dataclass
class SigningChecks:
    """
    Required signing checks for a PR.

    Attributes:
        pre_checks: Categories required before running tests (reset on every commit)
        extra_checks: Categories required before merging (reset on every commit)
    """

    pre_checks: List[str] = field(default_factory=list)
    extra_checks: List[str] = field(default_factory=list)


def get_signing_checks(repo_full_name: str, target_branch: str) -> SigningChecks:
    """
    Determine required signing checks based on repository and target branch.

    This centralizes the logic for determining which categories require signatures
    based on the repository type and target branch.

    Check requirements by repository:

    | Repository           | code-checks | orp | externals | tests |
    |----------------------|-------------|-----|-----------|-------|
    | cms-sw/cmssw (master)| PRE         | EXT | -         | EXT   |
    | cms-sw/cmssw (fwport)| PRE         | EXT | -         | EXT   |
    | cms-sw/cmssw (other) | -           | EXT | -         | EXT   |
    | cms-sw/cmsdist       | -           | EXT | EXT       | EXT*  |
    | cms-data/*           | -           | EXT | EXT       | EXT*  |
    | cms-externals/*      | -           | EXT | EXT       | EXT*  |
    | Non-CMS repos        | -           | -   | -         | EXT   |

    PRE = pre_check (required before tests)
    EXT = extra_check (required before merge)
    * = only if repo is in VALID_CMS_SW_REPOS_FOR_TESTS

    Args:
        repo_full_name: Full repository name (e.g., "cms-sw/cmssw")
        target_branch: Target branch for the PR (e.g., "master", "CMSSW_14_0_X")

    Returns:
        SigningChecks with pre_checks and extra_checks lists
    """
    pre_checks: List[str] = []
    extra_checks: List[str] = []

    # Parse repo org and name
    parts = repo_full_name.split("/", 1)
    if len(parts) != 2:
        # Invalid repo name, return minimal checks
        return SigningChecks(pre_checks=[], extra_checks=["tests"])

    repo_org, repo_name = parts

    # Determine repo type
    is_cmssw = repo_full_name == f"{GH_CMSSW_ORGANIZATION}/{GH_CMSSW_REPO}"
    is_cmsdist = repo_full_name == f"{GH_CMSSW_ORGANIZATION}/{GH_CMSDIST_REPO}"
    is_cms_org = repo_org in EXTERNAL_REPOS
    is_cms_data = repo_org == "cms-data"
    is_cms_externals = repo_org == "cms-externals"

    if is_cmssw:
        # cms-sw/cmssw repository
        # Check if target branch requires code-checks (master or forward-port branch)
        needs_code_checks = False
        if target_branch == "master":
            needs_code_checks = True
        else:
            # Check forward-ports map for this branch
            try:
                fwports = forward_ports_map.GIT_REPO_FWPORTS.get("cmssw", {})
                if target_branch in fwports.get(CMSSW_DEVEL_BRANCH, []):
                    needs_code_checks = True
            except Exception:
                pass

        if needs_code_checks:
            pre_checks.append("code-checks")

        extra_checks.extend(["orp", "tests"])

    elif is_cmsdist or is_cms_data or is_cms_externals:
        # cms-sw/cmsdist, cms-data/*, cms-externals/* repositories
        extra_checks.append("orp")
        extra_checks.append("externals")

        # tests only if in VALID_CMS_SW_REPOS_FOR_TESTS
        if repo_name in VALID_CMS_SW_REPOS_FOR_TESTS:
            extra_checks.append("tests")

    elif is_cms_org:
        # Other CMS organization repos (cms-sw/* except cmssw/cmsdist)
        extra_checks.append("orp")
        extra_checks.append("externals")

        # tests only if in VALID_CMS_SW_REPOS_FOR_TESTS
        if repo_name in VALID_CMS_SW_REPOS_FOR_TESTS:
            extra_checks.append("tests")

    else:
        # Non-CMS repos - only tests required
        extra_checks.append("tests")

    return SigningChecks(pre_checks=pre_checks, extra_checks=extra_checks)


def is_extra_check_category(context: "PRContext", category: str) -> bool:
    """
    Check if a category is an EXTRA_CHECK (or PRE_CHECK) category.

    These categories reset on every commit.

    Args:
        context: PR processing context
        category: Category name to check

    Returns:
        True if category is a PRE_CHECK or EXTRA_CHECK
    """
    signing_checks = context.get_signing_checks_for_pr()
    return category in signing_checks.pre_checks or category in signing_checks.extra_checks


# =============================================================================
# COMMAND REGISTRY WITH DECORATOR SUPPORT
# =============================================================================


@dataclass
class Command:
    """
    Definition of a bot command.

    Attributes:
        name: Command identifier
        pattern: Regex pattern to match the command
        handler: Function to execute when command matches.
                 Returns True for success, False for failure, or None to indicate
                 the command doesn't apply (allows fallthrough to other commands).
        acl: Access control (list of allowed users, L2 categories, or callback)
        description: Human-readable description
        pr_only: If True, command is only valid for PRs (not issues)
        reset_on_push: If True, command is skipped if comment is before latest commit
    """

    name: str
    pattern: re.Pattern
    handler: Callable[..., Optional[bool]]
    acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None
    description: str = ""
    pr_only: bool = False
    reset_on_push: bool = False


class CommandRegistry:
    """Registry for all bot commands with decorator support."""

    def __init__(self):
        self.commands: List[Command] = []

    def register(
        self,
        name: str,
        pattern: str,
        handler: Callable[..., bool],
        acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
        description: str = "",
        pr_only: bool = False,
        reset_on_push: bool = False,
    ) -> None:
        """Register a new command."""
        self.commands.append(
            Command(
                name=name,
                pattern=re.compile(pattern, re.IGNORECASE),
                handler=handler,
                acl=acl,
                description=description,
                pr_only=pr_only,
                reset_on_push=reset_on_push,
            )
        )

    def command(
        self,
        name: str,
        pattern: str,
        acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
        description: str = "",
        pr_only: bool = False,
        reset_on_push: bool = False,
    ) -> Callable[[Callable[..., Optional[bool]]], Callable[..., Optional[bool]]]:
        r"""
        Decorator to register a command handler.

        Usage:
            @registry.command("approve", r"^\+1$|^\+(\w+)$", description="Approve PR")
            def handle_approve(context, match, user, comment_id, timestamp) -> Optional[bool]:
                # ... handler logic ...
                return True  # Success, False = failure, None = fallthrough

        Args:
            name: Command identifier
            pattern: Regex pattern to match
            acl: Access control specification
            description: Human-readable description
            pr_only: If True, command only applies to PRs
            reset_on_push: If True, command is skipped if comment is before latest commit

        Returns:
            Decorator function
        """

        def decorator(func: Callable[..., Optional[bool]]) -> Callable[..., Optional[bool]]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Optional[bool]:
                return func(*args, **kwargs)

            self.register(name, pattern, wrapper, acl, description, pr_only, reset_on_push)
            return wrapper

        return decorator

    def find_command(self, text: str, is_pr: bool = True) -> Optional[Tuple[Command, re.Match]]:
        """
        Find a command matching the given text.

        DEPRECATED: Use find_commands() for fallthrough support.

        Args:
            text: Command text to match
            is_pr: True if this is a PR, False if it's an Issue

        Returns:
            Tuple of (Command, Match) or None
        """
        for cmd, match in self.find_commands(text, is_pr):
            return cmd, match
        return None

    def find_commands(
        self, text: str, is_pr: bool = True
    ) -> Generator[Tuple[Command, re.Match], None, None]:
        """
        Find all commands matching the given text.

        Yields commands in registration order, allowing handlers to return None
        to indicate fallthrough to the next matching command.

        Args:
            text: Command text to match
            is_pr: True if this is a PR, False if it's an Issue

        Yields:
            Tuple of (Command, Match) for each matching command
        """
        for cmd in self.commands:
            # Skip PR-only commands when processing issues
            if cmd.pr_only and not is_pr:
                continue
            match = cmd.pattern.match(text)
            if match:
                yield cmd, match


# Global command registry - commands register themselves via decorators
_global_registry = CommandRegistry()


def command(
    name: str,
    pattern: str,
    acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
    description: str = "",
    pr_only: bool = False,
    reset_on_push: bool = False,
) -> Callable[[Callable[..., Optional[bool]]], Callable[..., Optional[bool]]]:
    r"""
    Module-level decorator to register commands.

    Usage:
        @command("approve", r"^\+1$|^\+(\w+)$", description="Approve PR", pr_only=True)
        def handle_approve(context, match, user, comment_id, timestamp) -> Optional[bool]:
            return True  # Success, False = failure, None = fallthrough
    """
    return _global_registry.command(name, pattern, acl, description, pr_only, reset_on_push)


def get_global_registry() -> CommandRegistry:
    """Get the global command registry."""
    return _global_registry


# =============================================================================
# COMMAND PREPROCESSING
# =============================================================================


def preprocess_command(line: str, cmsbuild_user: Optional[str] = None) -> Tuple[str, bool]:
    """
    Preprocess a command line according to specification.

    - Normalize whitespace
    - Remove spaces around commas
    - Strip leading/trailing whitespace
    - Remove @cmsbuild_user and 'please' prefixes

    Args:
        line: The command line to preprocess
        cmsbuild_user: The bot username (for @mention detection)

    Returns:
        Tuple of (preprocessed_line, bot_was_mentioned)
    """
    # Normalize whitespace
    line = " ".join(line.split())

    # Remove spaces around commas
    line = re.sub(r"\s*,\s*", ",", line)

    # Strip leading/trailing whitespace
    line = line.strip()

    # Check if bot was mentioned and remove prefix
    _cmsbuild_user = cmsbuild_user or "cmsbuild"
    bot_pattern = rf"^(@?{re.escape(_cmsbuild_user)}\s?[,]*\s?)?(please\s?[,]*\s?)?"
    match = re.match(bot_pattern, line, flags=re.IGNORECASE)
    bot_mentioned = bool(match and match.group(1))
    line = re.sub(bot_pattern, "", line, flags=re.IGNORECASE)

    return line, bot_mentioned


def extract_command_line(
    comment_body: str, cmsbuild_user: Optional[str] = None
) -> Tuple[Optional[str], bool]:
    """
    Extract the first non-blank line from a comment for command parsing.

    Args:
        comment_body: The comment body text
        cmsbuild_user: The bot username (for @mention detection)

    Returns:
        Tuple of (command_line, bot_was_mentioned)
    """
    if not comment_body:
        return None, False

    for line in comment_body.split("\n"):
        stripped = line.strip()
        if stripped:
            return preprocess_command(stripped, cmsbuild_user)
    return None, False


# =============================================================================
# PR DESCRIPTION PARSING
# =============================================================================


def should_ignore_issue(repo_config: types.ModuleType, repo: Any, issue: Any) -> bool:
    """
    Check if issue/PR should be ignored based on various criteria.

    Returns True if:
    1. Issue number is in IGNORE_ISSUES config
    2. Issue number is in repo-specific IGNORE_ISSUES[repo.full_name]
    3. Issue title matches BUILD_REL pattern (release build issues)
    4. First line of body matches <cms-bot></cms-bot> or CMSBOT_IGNORE_MSG

    Args:
        repo_config: Repository configuration module
        repo: Repository object
        issue: Issue/PR object

    Returns:
        True if issue should be ignored, False otherwise
    """
    # Check IGNORE_ISSUES config
    ig_issues = getattr(repo_config, "IGNORE_ISSUES", {})

    # Check if issue number is directly in IGNORE_ISSUES
    if issue.number in ig_issues:
        return True

    # Check if issue number is in repo-specific ignore list
    repo_full_name = repo.full_name if hasattr(repo, "full_name") else ""
    if repo_full_name in ig_issues and issue.number in ig_issues[repo_full_name]:
        return True

    # Check if title matches BUILD_REL pattern (release build issues)
    if issue.title and re.match(BUILD_REL, issue.title):
        return True

    # Check if body has ignore marker on first line
    if issue.body:
        # Get first non-blank line
        try:
            first_line = issue.body.split("\n", 1)[0].strip()
            if first_line and RE_CMS_BOT_IGNORE.search(first_line):
                return True
        except Exception:
            pass

    return False


def should_ignore_pr_body(pr_body: str) -> bool:
    """
    Check if PR should be ignored based on description only.

    Returns True if first non-blank line matches <cms-bot></cms-bot>.

    Note: For full ignore checking including IGNORE_ISSUES and BUILD_REL,
    use should_ignore_issue() instead.
    """
    first_line, _ = extract_command_line(pr_body or "")
    if not first_line:
        return False
    return bool(RE_CMS_BOT_IGNORE.match(first_line))


def should_notify_without_at(pr_body: str) -> bool:
    """
    Check if notifications should omit @ symbol.

    Returns True if first non-blank line matches <notify></notify>.
    """
    first_line, _ = extract_command_line(pr_body or "")
    if not first_line:
        return False
    return bool(RE_NOTIFY_NO_AT.match(first_line))


# =============================================================================
# PR CONTEXT
# =============================================================================


@dataclass
class PRContext:
    """
    Context for processing a PR or Issue.

    Holds all state needed during PR/Issue processing.
    """

    repo_config: types.ModuleType  # Repository configuration module
    gh: Any  # GitHub instance
    repo: Any  # Repository
    issue: Any  # Issue/PR
    pr: Optional[Any]  # PullRequest (None for issues)
    cache: BotCache
    command_registry: CommandRegistry
    dry_run: bool
    cmsbuild_user: Optional[str]

    # Flag to indicate if this is a PR or Issue
    is_pr: bool = True

    # Comments fetched once at the start of processing
    comments: List[Any] = field(default_factory=list)

    # Commits fetched once at the start of processing (PRs only)
    commits: List[Any] = field(default_factory=list)

    # Processing state
    messages: List[str] = field(default_factory=list)
    should_merge: bool = False
    should_reopen: bool = False  # Reopen the issue/PR
    must_close: bool = False  # PR should be closed (e.g., closed branch)
    abort_tests: bool = False  # Abort pending tests
    tests_to_run: List[Any] = field(default_factory=list)  # List of TestRequest objects
    pending_reactions: Dict[int, str] = field(default_factory=dict)  # comment_id -> reaction
    holds: List[Hold] = field(default_factory=list)  # Active holds on the PR
    pending_labels: Set[str] = field(default_factory=set)  # Labels to add
    signing_categories: Set[str] = field(default_factory=set)  # Categories requiring signatures
    manually_assigned_categories: Set[str] = field(
        default_factory=set
    )  # Categories assigned via 'assign' command
    packages: Set[str] = field(default_factory=set)  # Packages touched by PR
    test_params: Dict[str, str] = field(default_factory=dict)  # Parameters from 'test parameters:'
    granted_test_rights: Set[str] = field(default_factory=set)  # Users granted test rights

    # Pending build/test commands - processed after all comments are seen
    # List of (verb, comment_id, user, timestamp, parsed_result) tuples
    pending_build_test_commands: List[Tuple[str, int, str, datetime, Any]] = field(
        default_factory=list
    )

    # Code checks
    code_checks_requested: bool = False
    code_checks_tool_conf: Optional[str] = None
    code_checks_apply_patch: bool = False

    # Test overrides
    ignore_tests_rejected: Optional[str] = None  # Reason for ignoring test rejection
    ignore_commit_count: bool = False  # Override commit count warning (+commit-count accepted)
    ignore_file_count: bool = False  # Override file count warning (+file-count accepted)
    warned_too_many_commits: bool = False  # Bot has already warned about commits
    warned_too_many_files: bool = False  # Bot has already warned about files
    blocked_by_commit_count: bool = False  # PR processing blocked by commit count
    blocked_by_file_count: bool = False  # PR processing blocked by file count

    # Backport info
    backport_of: Optional[str] = None  # PR number this is a backport of

    # Repository info - only _repo_name and _repo_org are stored
    _repo_name: str = ""
    _repo_org: str = ""
    create_test_property: bool = False  # Should create test properties?

    # PR description flags
    notify_without_at: bool = False  # If True, don't use @ when mentioning users

    # Message tracking (to avoid duplicate bot messages)
    posted_messages: Set[str] = field(default_factory=set)  # Message keys already posted

    # Pending bot comments to post at end of processing
    # List of (message, message_key, comment_id) tuples
    pending_bot_comments: List[Tuple[str, str, Optional[int]]] = field(default_factory=list)

    # Welcome message tracking
    welcome_message_posted: bool = False  # True if welcome message was posted

    # Watchers for this PR
    watchers: Set[str] = field(default_factory=set)  # Users watching files/categories

    # Changed files (cached from pr.get_files())
    _changed_files: Optional[List[str]] = field(default=None, repr=False)
    _pr_files_with_sha: Optional[Dict[str, str]] = field(default=None, repr=False)

    @property
    def repo_name(self) -> str:
        """Get repository name."""
        if self._repo_name:
            return self._repo_name
        return self.repo.name if self.repo else ""

    @repo_name.setter
    def repo_name(self, value: str) -> None:
        self._repo_name = value

    @property
    def repo_org(self) -> str:
        """Get repository organization."""
        if self._repo_org:
            return self._repo_org
        if self.repo and hasattr(self.repo.owner, "login"):
            return self.repo.owner.login
        return ""

    @repo_org.setter
    def repo_org(self, value: str) -> None:
        self._repo_org = value

    @property
    def cmssw_repo(self) -> bool:
        """Check if this is the main CMSSW repo."""
        return self.repo_name == GH_CMSSW_REPO

    @property
    def cms_repo(self) -> bool:
        """Check if this is a CMS organization repo."""
        return self.repo_org in EXTERNAL_REPOS

    @property
    def external_repo(self) -> bool:
        """Check if this is an external repo."""
        return self.repo_name != CMSSW_REPO_NAME and self.repo_org in EXTERNAL_REPOS

    @property
    def is_draft(self) -> bool:
        """Check if PR is in draft state."""
        if self.pr and hasattr(self.pr, "draft"):
            return self.pr.draft
        return False

    @property
    def repo_full_name(self) -> str:
        """Get full repository name (org/repo)."""
        if self.repo and hasattr(self.repo, "full_name"):
            return self.repo.full_name
        return f"{self.repo_org}/{self.repo_name}"

    @property
    def target_branch(self) -> str:
        """Get target branch for PR (empty string for issues)."""
        if self.pr and hasattr(self.pr, "base") and hasattr(self.pr.base, "ref"):
            return self.pr.base.ref
        return ""

    def get_signing_checks_for_pr(self) -> "SigningChecks":
        """
        Get signing checks for this PR based on repository and target branch.

        Returns:
            SigningChecks with pre_checks and extra_checks lists
        """
        return get_signing_checks(self.repo_full_name, self.target_branch)


def format_mention(context: PRContext, username: str) -> str:
    """
    Format a username for mentioning in a comment.

    Omits @ symbol if:
    - PR has <notify></notify> in its description
    - PR is in draft state

    Args:
        context: PR processing context
        username: GitHub username to mention

    Returns:
        Formatted mention string (with or without @)
    """
    if context.notify_without_at or context.is_draft:
        return username
    return f"@{username}"


def post_bot_comment(
    context: PRContext,
    message: str,
    message_key: str,
    comment_id: Optional[int] = None,
) -> bool:
    """
    Queue a bot comment to be posted at the end of processing.

    Checks if a message with the same key (tied to a comment_id if provided)
    has already been posted or queued. If so, skips queuing.

    Messages are queued and posted later by flush_pending_comments() to allow
    later commands to potentially cancel or modify earlier messages.

    Args:
        context: PR processing context
        message: The message to post
        message_key: Unique key identifying the message type
        comment_id: Optional comment ID this message is in response to

    Returns:
        True if message was queued, False if skipped (duplicate)
    """
    # Build full key including comment_id if provided
    full_key = f"{message_key}:{comment_id}" if comment_id else message_key

    # Check if already posted (scan existing comments for this message pattern)
    for comment in context.comments:
        if context.cmsbuild_user and comment.user.login == context.cmsbuild_user:
            body = comment.body or ""
            # Check if this comment contains our message key marker
            if f"<!--{full_key}-->" in body:
                logger.debug(f"Skipping duplicate message: {full_key}")
                return False

    # Check if we've already queued this message in current run
    if full_key in context.posted_messages:
        logger.debug(f"Message already queued: {full_key}")
        return False

    # Mark as queued
    context.posted_messages.add(full_key)

    # Queue the message for later posting
    context.pending_bot_comments.append((message, message_key, comment_id))
    logger.debug(f"Queued message: {full_key}")

    return True


def cancel_pending_comment(
    context: PRContext, message_key: str, comment_id: Optional[int] = None
) -> bool:
    """
    Cancel a pending bot comment that hasn't been posted yet.

    Args:
        context: PR processing context
        message_key: Key identifying the message type to cancel
        comment_id: Optional comment ID the message was in response to

    Returns:
        True if a message was cancelled, False if not found
    """
    full_key = f"{message_key}:{comment_id}" if comment_id else message_key

    # Find and remove the pending comment
    for i, (msg, key, cid) in enumerate(context.pending_bot_comments):
        pending_key = f"{key}:{cid}" if cid else key
        if pending_key == full_key:
            context.pending_bot_comments.pop(i)
            context.posted_messages.discard(full_key)
            logger.debug(f"Cancelled pending message: {full_key}")
            return True

    return False


def flush_pending_comments(context: PRContext) -> int:
    """
    Post all pending bot comments.

    Should be called at the end of PR processing after all commands
    have been processed.

    Args:
        context: PR processing context

    Returns:
        Number of comments actually posted
    """
    posted_count = 0

    for message, message_key, comment_id in context.pending_bot_comments:
        full_key = f"{message_key}:{comment_id}" if comment_id else message_key

        # Add invisible marker to message for future detection
        marked_message = f"{message}\n<!--{full_key}-->"

        if context.dry_run:
            logger.info(f"[DRY RUN] Would post comment: {message[:100]}...")
            continue

        try:
            context.issue.create_comment(marked_message)
            logger.info(f"Posted comment: {message_key}")
            posted_count += 1
        except Exception as e:
            logger.error(f"Failed to post comment: {e}")

    # Clear the queue
    context.pending_bot_comments.clear()

    return posted_count


# =============================================================================
# COMMAND HANDLERS (registered via decorators)
# =============================================================================

# Category name pattern: word characters and hyphens (e.g., code-checks, l1-trigger)
CATEGORY_PATTERN = r"[\w-]+"


@command(
    "approve",
    rf"^\+1$|^\+({CATEGORY_PATTERN})$",
    description="Approve PR for your L2 categories or specific category",
    pr_only=True,
)
def handle_plus_one(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> Optional[bool]:
    """Handle +1 or +<category> approval."""
    return _handle_approval(context, match, user, comment_id, timestamp, approved=True)


@command(
    "reject",
    rf"^-1$|^-({CATEGORY_PATTERN})$",
    description="Reject PR for your L2 categories or specific category",
    pr_only=True,
)
def handle_minus_one(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> Optional[bool]:
    """Handle -1 or -<category> rejection."""
    return _handle_approval(context, match, user, comment_id, timestamp, approved=False)


def _handle_approval(
    context: PRContext,
    match: re.Match,
    user: str,
    comment_id: int,
    timestamp: datetime,
    approved: bool,
) -> Optional[bool]:
    """
    Handle +1/-1 or +category/-category commands.

    Args:
        context: PR processing context
        match: Regex match object
        user: Username who made the comment
        comment_id: ID of the comment
        timestamp: When the comment was made
        approved: True for approval, False for rejection

    Returns:
        True if approval was recorded
        False if user lacks permission
        None if the category is not a signing category (allows fallthrough)
    """
    category_str = match.group(1) if match.lastindex and match.group(1) else None

    # Determine which categories this signature applies to
    if category_str:
        # Specific category - check if it's a valid signing category
        category = category_str.strip()
        if category not in context.signing_categories:
            # Not a signing category - return None to allow fallthrough to other commands
            logger.debug(f"Category '{category}' is not a signing category, allowing fallthrough")
            return None
        categories = [category]
    else:
        # Generic +1/-1 applies to all user's L2 categories at that time
        categories = get_user_l2_categories(context.repo_config, user, timestamp)

    if not categories:
        logger.info(f"User {user} has no L2 categories to sign with")
        return False

    # Get current file versions for the categories being signed
    # A signature is valid only if these exact file versions are still current
    signed_files = get_files_for_categories(context, categories)

    # Update comment info in cache
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line="+1" if approved else "-1",
        ctype="+1" if approved else "-1",
        categories=categories,
        signed_files=signed_files,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

    logger.info(
        f"Recorded {'approval' if approved else 'rejection'} from {user} "
        f"for categories: {categories} (signed {len(signed_files)} files)"
    )
    return True


@command(
    "assign_category",
    rf"^assign (?P<categories>(?:{CATEGORY_PATTERN})(?:,(?:{CATEGORY_PATTERN}))*)$",
    description="Assign categories for review (comma-separated)",
    pr_only=True,
)
def handle_assign_category(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle assign <category>[,<category>,...] command."""
    return _handle_assign(context, match, user, comment_id, timestamp, from_packages=False)


@command(
    "assign_from_package",
    r"^assign from (?P<packages>[\w/,-]+(?:,[\w/,-]+)*)$",
    description="Assign categories based on package mapping (comma-separated)",
    pr_only=True,
)
def handle_assign_from_package(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle assign from <package>[,<package>,...] command."""
    return _handle_assign(context, match, user, comment_id, timestamp, from_packages=True)


def _handle_assign(
    context: PRContext,
    match: re.Match,
    user: str,
    comment_id: int,
    timestamp: datetime,
    from_packages: bool = False,
) -> bool:
    """
    Handle assign command.

    Syntax:
    - assign <category>[,<category>,...]
    - assign from <package>[,<package>,...]

    Args:
        context: PR processing context
        match: Regex match object
        user: Username who made the comment
        comment_id: ID of the comment
        timestamp: When the comment was made
        from_packages: If True, input is package names to map to categories

    Returns:
        True if at least one category was assigned, False otherwise
    """
    groups = match.groupdict()

    if from_packages:
        # Map packages to categories
        packages_str = groups.get("packages", "")
        packages = [p.strip() for p in packages_str.split(",") if p.strip()]

        if not packages:
            logger.warning("No packages specified for assign from command")
            return False

        categories = []
        invalid_packages = []

        for pkg in packages:
            cat = get_package_category(context.repo_config, pkg)
            if cat:
                if cat not in categories:
                    categories.append(cat)
            else:
                invalid_packages.append(pkg)

        if invalid_packages:
            logger.warning(
                f"No category mapping found for packages: {', '.join(invalid_packages)}"
            )
            context.messages.append(f"Unknown packages: {', '.join(invalid_packages)}")

        if not categories:
            return False
    else:
        # Direct category assignment
        categories_str = groups.get("categories", "")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()]

        if not categories:
            logger.warning("No categories specified for assign command")
            return False

        # Validate categories exist in CMSSW_CATEGORIES
        valid_categories = []
        invalid_categories = []

        for cat in categories:
            if cat in CMSSW_CATEGORIES:
                valid_categories.append(cat)
            else:
                invalid_categories.append(cat)

        if invalid_categories:
            logger.warning(f"Invalid categories: {', '.join(invalid_categories)}")
            context.messages.append(f"Unknown categories: {', '.join(invalid_categories)}")

        if not valid_categories:
            return False

        categories = valid_categories

    # Determine which categories are truly new
    new_categories = [cat for cat in categories if cat not in context.signing_categories]

    if new_categories:
        # Add new categories to signing_categories
        context.signing_categories.update(new_categories)

        # Track these as manually assigned (for unassign command)
        context.manually_assigned_categories.update(new_categories)

        # Get L2s for the new categories
        new_l2s = set()
        for cat in new_categories:
            cat_l2s = get_category_l2s(context.repo_config, cat, timestamp)
            new_l2s.update(cat_l2s)

        # Post message about new categories
        if new_l2s:
            l2_mentions = ", ".join(format_mention(context, l2) for l2 in sorted(new_l2s))
            msg = (
                f"New categories assigned: {', '.join(new_categories)}\n\n"
                f"{l2_mentions} you have been requested to review this Pull request/Issue "
                "and eventually sign. Thanks"
            )
            post_bot_comment(context, msg, "assign", comment_id)

    logger.info(f"Assigned categories: {', '.join(categories)}")
    return True


@command(
    "unassign_category",
    rf"^unassign (?P<categories>(?:{CATEGORY_PATTERN})(?:,(?:{CATEGORY_PATTERN}))*)$",
    description="Remove category assignment (comma-separated)",
    pr_only=True,
)
def handle_unassign_category(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle unassign <category>[,<category>,...] command."""
    return _handle_unassign(context, match, user, comment_id, timestamp, from_packages=False)


@command(
    "unassign_from_package",
    r"^unassign from (?P<packages>[\w/,-]+(?:,[\w/,-]+)*)$",
    description="Remove category assignment based on package (comma-separated)",
    pr_only=True,
)
def handle_unassign_from_package(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle unassign from <package>[,<package>,...] command."""
    return _handle_unassign(context, match, user, comment_id, timestamp, from_packages=True)


def _handle_unassign(
    context: PRContext,
    match: re.Match,
    user: str,
    comment_id: int,
    timestamp: datetime,
    from_packages: bool = False,
) -> bool:
    """
    Handle unassign command.

    Only removes categories that were manually assigned via 'assign' command.
    Categories that are automatically assigned based on file changes cannot
    be unassigned.

    Syntax:
    - unassign <category>[,<category>,...]
    - unassign from <package>[,<package>,...]

    Args:
        context: PR processing context
        match: Regex match object
        user: Username who made the comment
        comment_id: ID of the comment
        timestamp: When the comment was made
        from_packages: If True, input is package names to map to categories

    Returns:
        True if at least one category was unassigned, False otherwise
    """
    groups = match.groupdict()

    if from_packages:
        # Map packages to categories
        packages_str = groups.get("packages", "")
        packages = [p.strip() for p in packages_str.split(",") if p.strip()]

        if not packages:
            logger.warning("No packages specified for unassign from command")
            return False

        categories = []
        invalid_packages = []

        for pkg in packages:
            cat = get_package_category(context.repo_config, pkg)
            if cat:
                if cat not in categories:
                    categories.append(cat)
            else:
                invalid_packages.append(pkg)

        if invalid_packages:
            logger.warning(
                f"No category mapping found for packages: {', '.join(invalid_packages)}"
            )
            context.messages.append(f"Unknown packages: {', '.join(invalid_packages)}")

        if not categories:
            return False
    else:
        # Direct category unassignment
        categories_str = groups.get("categories", "")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()]

        if not categories:
            logger.warning("No categories specified for unassign command")
            return False

        # Validate categories exist in CMSSW_CATEGORIES
        valid_categories = []
        invalid_categories = []

        for cat in categories:
            if cat in CMSSW_CATEGORIES:
                valid_categories.append(cat)
            else:
                invalid_categories.append(cat)

        if invalid_categories:
            logger.warning(f"Invalid categories: {', '.join(invalid_categories)}")
            context.messages.append(f"Unknown categories: {', '.join(invalid_categories)}")

        if not valid_categories:
            return False

        categories = valid_categories

    # Only remove categories that were manually assigned
    # Categories from file changes cannot be unassigned
    removable = []
    not_manually_assigned = []

    for cat in categories:
        if cat in context.manually_assigned_categories:
            removable.append(cat)
        else:
            not_manually_assigned.append(cat)

    if not_manually_assigned:
        logger.warning(
            f"Cannot unassign categories that were not manually assigned: "
            f"{', '.join(not_manually_assigned)}"
        )
        context.messages.append(
            f"Cannot unassign categories (not manually assigned): "
            f"{', '.join(not_manually_assigned)}"
        )

    if not removable:
        return False

    # Remove categories from both signing_categories and manually_assigned_categories
    for cat in removable:
        context.signing_categories.discard(cat)
        context.manually_assigned_categories.discard(cat)

    logger.info(f"Unassigned categories: {', '.join(removable)}")
    return True


@command("hold", r"^hold$", description="Place a hold to prevent automerge", pr_only=True)
def handle_hold(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle hold command - prevents automerge.

    Can be used by:
    - Users with L2 signing categories
    - Release managers
    - PR hold managers (PR_HOLD_MANAGERS)
    """
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)

    # Check if user is a release manager
    is_release_manager = False
    if context.pr:
        try:
            release_managers = get_release_managers(context.pr.base.ref)
            is_release_manager = user in release_managers
        except Exception:
            pass

    # Check if user is a PR hold manager
    is_hold_manager = user in PR_HOLD_MANAGERS

    # User must have L2 categories, be a release manager, or be a hold manager
    if not user_categories and not is_release_manager and not is_hold_manager:
        logger.info(
            f"User {user} cannot place hold (no L2 categories, not release manager, not hold manager)"
        )
        return False

    # Determine which category to use for the hold
    if user_categories:
        # Use L2 categories
        hold_categories = user_categories
    elif is_release_manager:
        # Release managers use a special category
        hold_categories = ["release-manager"]
    else:
        # Hold managers use a special category
        hold_categories = ["hold-manager"]

    # Place hold for each category
    for category in hold_categories:
        hold = Hold(category=category, user=user, comment_id=comment_id)
        context.holds.append(hold)
        logger.info(f"Hold placed by {user} ({category})")

    # Post hold notification
    blockers = format_mention(context, user)
    msg = (
        f"Pull request has been put on hold by {blockers}\n"
        "They need to issue an `unhold` command to remove the `hold` state "
        "or L1 can `unhold` it for all"
    )
    post_bot_comment(context, msg, "hold", comment_id)

    return True


@command(
    "unhold",
    r"^unhold$",
    description="Remove hold (L2 for own category, ORP for all)",
    pr_only=True,
)
def handle_unhold(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle unhold command.

    - ORP members can remove ALL holds
    - L2 members can remove their own holds only
    - Release managers can remove their own holds only
    - PR hold managers can remove their own holds only
    """
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)
    is_orp = "orp" in [c.lower() for c in user_categories]

    if is_orp:
        # ORP unhold removes ALL holds
        removed_count = len(context.holds)
        # Cancel any pending hold messages
        for hold in context.holds:
            cancel_pending_comment(context, "hold", hold.comment_id)
        context.holds = []
        logger.info(f"ORP user {user} removed all {removed_count} holds")
        return True  # ORP unhold always succeeds

    # Build list of categories this user can unhold
    # Users can only remove their own holds
    removable_categories = set(user_categories)

    # Check if user is a release manager
    if context.pr:
        try:
            release_managers = get_release_managers(context.pr.base.ref)
            if user in release_managers:
                removable_categories.add("release-manager")
        except Exception:
            pass

    # Check if user is a PR hold manager
    if user in PR_HOLD_MANAGERS:
        removable_categories.add("hold-manager")

    if not removable_categories:
        logger.info(f"User {user} cannot unhold (no permissions)")
        return False

    # Remove holds that match user's categories AND were placed by this user
    # Also cancel pending hold messages for removed holds
    original_count = len(context.holds)
    new_holds = []
    for h in context.holds:
        if h.category in removable_categories and h.user == user:
            # This hold is being removed, cancel its pending message
            cancel_pending_comment(context, "hold", h.comment_id)
        else:
            new_holds.append(h)
    context.holds = new_holds
    removed = original_count - len(context.holds)

    if removed > 0:
        logger.info(f"User {user} removed {removed} hold(s)")
        return True
    else:
        logger.info(f"User {user} had no holds to remove")
        return False


@command("merge", r"^merge$", description="Request merge of the PR", pr_only=True)
def handle_merge(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle merge command."""
    if not can_merge(context):
        logger.info("Merge conditions not met")
        context.messages.append("Cannot merge: PR is not ready for merge")
        return False

    context.should_merge = True
    logger.info(f"Merge requested by {user}")

    # Note: merge commands are not cached - only signatures (+1/-1) are cached
    return True


@command("close", r"^close$", description="Close the PR/Issue")
def handle_close(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle close command.

    Can be used by L2s, release managers, and issue trackers.
    """
    # ACL check would be done at command dispatch level
    context.must_close = True
    logger.info(f"Close requested by {user}")
    return True


@command("reopen", r"^(?:re)?open$", description="Reopen the PR/Issue")
def handle_reopen(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle open/reopen command.

    Can be used by L2s, release managers, and issue trackers.
    """
    context.should_reopen = True
    logger.info(f"Reopen requested by {user}")
    return True


def is_valid_tester(context: PRContext, user: str, timestamp: datetime) -> bool:
    """
    Check if a user is allowed to trigger tests.

    A user is a valid tester if ANY of these conditions is true:
    1. User is in TRIGGER_PR_TESTS list
    2. User is a release manager for the target branch
    3. User is the repository organization
    4. User is an L2 signer (has any category assignment)
    5. User has been granted test rights via 'allow @user test rights'

    Args:
        context: PR processing context
        user: Username to check
        timestamp: Timestamp for L2 membership check

    Returns:
        True if user can trigger tests
    """
    # Check if user is in TRIGGER_PR_TESTS
    if user in TRIGGER_PR_TESTS:
        return True

    # Check if user is a release manager
    if context.pr:
        release_managers = get_release_managers(context.pr.base.ref)
        if user in release_managers:
            return True

    # Check if user is the repo organization
    if user == context.repo_org:
        return True

    # Check if user has L2 categories
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)
    if user_categories:
        return True

    # Check if user has been granted test rights
    if user in context.granted_test_rights:
        return True

    return False


@command(
    "abort",
    r"^abort( test)?$",
    acl=is_valid_tester,
    description="Abort pending tests",
    pr_only=True,
    reset_on_push=True,
)
def handle_abort(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle abort/abort test command.

    Aborts any pending tests for the PR.
    Only takes effect if tests are actually running (not just pending/not started).
    """
    # Check if there are tests to abort (tests must be in pending state)
    statuses = get_ci_test_statuses(context)
    has_pending_tests = False

    for suffix, results in statuses.items():
        for result in results:
            if result.status == "pending":
                has_pending_tests = True
                break
        if has_pending_tests:
            break

    if not has_pending_tests:
        logger.info(f"Ignoring abort from {user} - no pending tests")
        return False

    context.abort_tests = True
    logger.info(f"Test abort requested by {user}")
    return True


@command("urgent", r"^urgent$", description="Mark PR as urgent")
def handle_urgent(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle urgent command.

    Can be used by L2s, release managers, or the PR author.
    """
    context.pending_labels.add("urgent")
    logger.info(f"PR marked as urgent by {user}")
    return True


@command(
    "backport",
    r"^backport (of )?#?(?P<pr_num>[1-9][0-9]*)$",
    description="Mark PR as backport of another PR",
)
def handle_backport(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle backport [of] #<num> command.

    Marks this PR as a backport of the specified PR.
    Updates the welcome message to include backport info.
    Adds 'backport' label, or 'backport-ok' if original PR is merged.
    """
    pr_num_str = match.group("pr_num")

    # Validate PR number format (already validated by regex, but double-check)
    if not pr_num_str or not pr_num_str.isdigit():
        logger.warning(f"Invalid backport PR number: {pr_num_str}")
        return False

    pr_num = int(pr_num_str)

    # Try to find the original PR
    try:
        original_pr = context.repo.get_pull(pr_num)
        if original_pr:
            context.backport_of = pr_num_str
            if original_pr.merged:
                context.pending_labels.add("backport-ok")
                logger.info(f"PR marked as backport of merged #{pr_num} by {user}")
            else:
                context.pending_labels.add("backport")
                logger.info(f"PR marked as backport of #{pr_num} by {user}")
            return True
    except Exception as e:
        logger.warning(f"Could not find original PR #{pr_num}: {e}")

    # Original PR not found - don't add backport label
    logger.info(f"Backport command for #{pr_num} - original PR not found, skipping label")
    return False


@command(
    "allow_test_rights",
    r"^allow @(?P<username>[^ ]+) test rights$",
    description="Grant test rights to a user",
    pr_only=True,
)
def handle_allow_test_rights(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle 'allow @<user> test rights' command.

    Can only be used by L2s and release managers.
    Grants the specified user permission to trigger tests.
    """
    target_user = match.group("username")
    context.granted_test_rights.add(target_user)
    logger.info(f"Test rights granted to {target_user} by {user}")
    return True


@command(
    "code_checks",
    r"^code-checks( with (?P<tool_conf>\S+))?( and apply patch)?$",
    description="Request code checks",
    pr_only=True,
)
def handle_code_checks(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle code-checks command.

    Triggers code style/format checks on the PR.
    Optionally can specify tool configuration and apply patch.
    """
    tool_conf = match.group("tool_conf") if match.lastindex else None
    apply_patch = "apply patch" in (match.group(0) or "").lower()

    context.code_checks_requested = True
    context.code_checks_tool_conf = tool_conf
    context.code_checks_apply_patch = apply_patch

    logger.info(
        f"Code checks requested by {user}"
        + (f" with {tool_conf}" if tool_conf else "")
        + (" (apply patch)" if apply_patch else "")
    )
    return True


@command(
    "ignore_tests_rejected",
    r"^ignore tests-rejected (with )?(?P<reason>[\w-]+)$",
    description="Override test failure with reason",
    pr_only=True,
    reset_on_push=True,
)
def handle_ignore_tests_rejected(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle 'ignore tests-rejected with <reason>' command.

    Allows overriding a test failure with a valid reason.
    Valid reasons are defined in githublabels.TEST_IGNORE_REASON.
    """
    reason = match.group("reason")

    # Validate reason against TEST_IGNORE_REASON
    if reason not in TEST_IGNORE_REASON:
        logger.warning(f"Invalid test ignore reason: {reason}")
        return False

    context.ignore_tests_rejected = reason
    logger.info(f"Test rejection ignored by {user} with reason: {reason}")
    return True


@command(
    "commit_count_override",
    r"^\+commit-count$",
    acl=CMSSW_ISSUES_TRACKERS,
    description="Ignore 'too many commits' warning",
    pr_only=True,
)
def handle_commit_count_override(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle +commit-count command.

    Overrides the 'too many commits' warning. Only CMSSW_ISSUES_TRACKERS can use this.
    Only works if commit count is below the FAIL threshold.
    """
    if not context.pr:
        return False

    commit_count = context.pr.commits
    if commit_count >= TOO_MANY_COMMITS_FAIL_THRESHOLD:
        context.messages.append(
            f"Cannot override: commit count ({commit_count}) is at or above "
            f"the hard limit ({TOO_MANY_COMMITS_FAIL_THRESHOLD})"
        )
        logger.warning(
            f"Cannot override commit count: {commit_count} >= {TOO_MANY_COMMITS_FAIL_THRESHOLD}"
        )
        return False

    context.ignore_commit_count = True
    logger.info(f"Commit count warning overridden by {user}")
    return True


@command(
    "file_count_override",
    r"^\+file-count$",
    acl=CMSSW_ISSUES_TRACKERS,
    description="Ignore 'too many files' warning",
    pr_only=True,
)
def handle_file_count_override(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle +file-count command.

    Overrides the 'too many files' warning. Only CMSSW_ISSUES_TRACKERS can use this.
    Only works if file count is below the FAIL threshold.
    """
    if not context.pr:
        return False

    file_count = context.pr.changed_files
    if file_count >= TOO_MANY_FILES_FAIL_THRESHOLD:
        context.messages.append(
            f"Cannot override: file count ({file_count}) is at or above "
            f"the hard limit ({TOO_MANY_FILES_FAIL_THRESHOLD})"
        )
        logger.warning(
            f"Cannot override file count: {file_count} >= {TOO_MANY_FILES_FAIL_THRESHOLD}"
        )
        return False

    context.ignore_file_count = True
    logger.info(f"File count warning overridden by {user}")
    return True


@command(
    "type",
    r"^type (?P<label>[\w-]+)$",
    description="Add a type label to the PR/Issue",
)
def handle_type(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle type <label> command.

    Adds a non-blocking label to the PR/Issue. The label must be defined
    in TYPE_COMMANDS to be valid.

    Labels have two modes:
    - 'type': Only the last one applies (replaces previous type labels)
    - 'mtype': Accumulates (multiple can coexist)

    Syntax:
        type <label>

    Examples:
        type bug-fix
        type new-feature
        type documentation
    """
    label = match.group("label")

    # Validate label is in TYPE_COMMANDS
    if label not in TYPE_COMMANDS:
        valid_labels = ", ".join(sorted(TYPE_COMMANDS.keys()))
        context.messages.append(f"Invalid type label '{label}'. Valid labels: {valid_labels}")
        logger.warning(f"Invalid type label: {label}")
        return False

    # Get label type (type or mtype)
    # TYPE_COMMANDS[label] = [color, regexp, label_type]
    label_info = TYPE_COMMANDS[label]
    label_type = label_info[2] if len(label_info) > 2 else "mtype"

    if label_type == "type":
        # 'type' labels replace previous - remove other 'type' labels
        type_labels_to_remove = set()
        for existing_label in context.pending_labels:
            if existing_label in TYPE_COMMANDS:
                existing_info = TYPE_COMMANDS[existing_label]
                existing_type = existing_info[2] if len(existing_info) > 2 else "mtype"
                if existing_type == "type":
                    type_labels_to_remove.add(existing_label)

        context.pending_labels -= type_labels_to_remove
        if type_labels_to_remove:
            logger.debug(f"Removed previous type labels: {type_labels_to_remove}")

    # Add the new label
    context.pending_labels.add(label)
    logger.info(f"Type label '{label}' ({label_type}) added by {user}")

    # Note: type commands are not cached - only signatures (+1/-1) are cached
    return True


# =============================================================================
# BUILD/TEST COMMAND PARSING
# =============================================================================


def parse_test_cmd(first_line: str) -> TestCmdResult:
    """
    Parse a build/test command line.

    Syntax:
        build|test [workflows <wf_list>] [with <pr_list>] [for <queue>]
                   [using [full cmssw] [addpkg <pkg_list>]]

    Args:
        first_line: The command line to parse

    Returns:
        TestCmdResult with parsed parameters

    Raises:
        TestCmdParseError: If parsing fails
    """
    tokens = first_line.strip().split()
    if not tokens:
        raise TestCmdParseError("empty input")

    seen: Set[re.Pattern] = set()
    res = TestCmdResult(verb=tokens.pop(0).lower())

    if res.verb not in TEST_VERBS:
        raise TestCmdParseError(f"Unknown verb: {res.verb}")

    params: List[TestCmdParam] = [
        TestCmdParam(
            keyword=r"workflows?",
            rx=RE_WF_LIST,
            split_by=",",
            field_name="workflows",
        ),
        TestCmdParam(
            keyword=r"with",
            rx=RE_PR_LIST,
            split_by=",",
            field_name="prs",
        ),
        TestCmdParam(
            keyword=r"for",
            rx=RE_QUEUE,
            split_by=None,
            field_name="queue",
        ),
        TestCmdParam(
            keyword=r"using",
            rx=None,
            field_name="using",
            split_by=None,
        ),
        TestCmdParam(
            keyword=r"full",
            rx=r"cmssw",
            split_by=None,
            field_name="full",
            prev_keyword=r"using",
        ),
        TestCmdParam(
            keyword=r"(cms-)?addpkg",
            rx=RE_PKG_LIST,
            split_by=",",
            field_name="addpkg",
            prev_keyword=r"using",
        ),
    ]

    t: Optional[str] = None
    prev_t: Optional[str] = None

    while tokens:
        prev_t = t
        t = tokens.pop(0)

        matched = False
        for p in params:
            if not p.keyword.match(t):
                continue

            if p.keyword in seen:
                raise TestCmdParseError(f"Duplicate {t} clause")

            next_val: Any = True

            if p.prev_keyword:
                if not prev_t or not p.prev_keyword.fullmatch(prev_t):
                    raise TestCmdParseError(
                        f"Keyword {t} must be preceded by {p.prev_keyword.pattern}"
                    )

            if p.rx or p.split_by:
                try:
                    next_val = tokens.pop(0)
                except IndexError:
                    raise TestCmdParseError(f"Missing parameter for keyword {t}")

                if p.rx and not p.rx.fullmatch(next_val):
                    raise TestCmdParseError(f"Invalid parameter for keyword {t}: {next_val!r}")

                if p.split_by:
                    next_val = next_val.split(p.split_by)

            setattr(res, p.field_name, next_val)
            seen.add(p.keyword)
            matched = True
            break

        if not matched:
            raise TestCmdParseError(f"Unexpected token: {t!r}")

    if res.using and not (res.addpkg or res.full):
        raise TestCmdParseError("Empty using statement")

    return res


# Cache for check functions (populated on first use)
_CHECK_FUNCTIONS: Optional[Dict[str, Callable]] = None


def get_check_functions() -> Dict[str, Callable]:
    """
    Get all check_* functions for parameter validation.

    Returns:
        Dict mapping function names to callables
    """
    global _CHECK_FUNCTIONS
    if _CHECK_FUNCTIONS is None:
        all_globals = globals()
        _CHECK_FUNCTIONS = {
            name: func
            for name, func in all_globals.items()
            if name.startswith("check_") and callable(func)
        }
    return _CHECK_FUNCTIONS


def parse_test_parameters(comment_lines: List[str], repo) -> Dict[str, str]:
    """
    Parse test parameters from a multi-line comment.

    Each line (after the first) should be in format: key = value
    Lines can optionally start with - or * (list markers).

    Args:
        comment_lines: Lines of the comment (first line is 'test parameters')
        repo: Repository object for validation functions

    Returns:
        Dict of parsed parameters, or {"errors": "..."} if parsing failed
    """
    errors: Dict[str, List[str]] = {"format": [], "key": [], "value": []}
    matched_params: Dict[str, str] = {}
    check_functions = get_check_functions()

    for line in comment_lines[1:]:  # Skip first line ('test parameters')
        line = line.strip()

        # Remove list markers
        if line.startswith(("-", "*")):
            line = line[1:].strip()

        if not line:
            continue

        # Parse key=value format
        if "=" not in line:
            errors["format"].append(f"'{line}'")
            continue

        key, value = line.split("=", 1)
        key = key.replace(" ", "")  # Remove spaces from key
        value = value.strip()

        # Match against MULTILINE_COMMENTS_MAP
        matched = False
        for pattern, config in MULTILINE_COMMENTS_MAP.items():
            if not re.fullmatch(pattern, key, re.IGNORECASE):
                continue

            # config is (value_pattern, param_name, [preserve_spaces])
            value_pattern = config[0]
            param_name = config[1]
            preserve_spaces = len(config) >= 3 and config[2]

            if not preserve_spaces:
                value = value.replace(" ", "")

            # Validate value against pattern
            if not re.fullmatch(value_pattern, value, re.IGNORECASE):
                errors["value"].append(key)
                matched = True
                break

            # Run check function if available
            check_func_name = f"check_{param_name.lower()}"
            if check_func_name in check_functions:
                try:
                    value, new_param = check_functions[check_func_name](
                        value, repo, matched_params, key, param_name
                    )
                    if new_param:
                        param_name = new_param
                except Exception:
                    pass

            matched_params[param_name] = value
            matched = True
            break

        if not matched:
            errors["key"].append(key)

    # Format error message if any errors occurred
    error_parts = []
    for error_type in sorted(errors.keys()):
        if errors[error_type]:
            error_parts.append(f"{error_type}:{','.join(errors[error_type])}")

    if error_parts:
        return {"errors": "ERRORS: " + "; ".join(error_parts)}

    return matched_params


@command(
    "test_parameters",
    r"^test parameters:$",
    acl=is_valid_tester,
    description="Set test parameters (multi-line)",
    pr_only=True,
)
def handle_test_parameters(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle 'test parameters:' command.

    This command processes a multi-line comment to set test parameters.
    Each line after 'test parameters:' should be in format: key = value

    Example:
        test parameters:
        - WORKFLOWS = 1.0,2.0
        - PULL_REQUESTS = cms-sw/cmssw#12345
        - ARCHITECTURE = el8_amd64_gcc12

    The parameters are stored in context for later use when triggering tests.
    Note: The 'test' command values override these for overlapping parameters.
    """
    # Get the full comment body to parse all lines
    comment_body = None
    for comment in context.comments:
        if comment.id == comment_id:
            comment_body = comment.body
            break

    if not comment_body:
        logger.warning(f"Could not find comment body for comment {comment_id}")
        return False

    # Split into lines
    lines = comment_body.split("\n")

    # Parse parameters
    params = parse_test_parameters(lines, context.repo)

    if "errors" in params:
        context.messages.append(params["errors"])
        logger.warning(f"Test parameters parsing errors: {params['errors']}")
        return False

    # Store parameters in context for later use
    context.test_params.update(params)

    logger.info(f"Test parameters set by {user}: {params}")
    return True


@command(
    "build_test",
    r"^(build|test)\b",
    acl=is_valid_tester,
    description="Trigger CI build/test",
    pr_only=True,
    reset_on_push=True,
)
def handle_build_test(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle build/test command - collects for deferred processing.

    Commands are collected during comment processing and processed later by
    process_pending_build_test_commands() after all comments are seen.

    For 'test': Last one wins (only the last test command is processed)
    For 'build': Skipped if comment already has +1 reaction from bot

    Syntax:
        build|test [workflows <wf_list>] [with <pr_list>] [for <queue>]
                   [using [full cmssw] [addpkg <pkg_list>]]
    """
    # Get the full command line from the comment
    first_line = match.group(0)

    # Try to get full first line from the actual comment
    for comment in context.comments:
        if comment.id == comment_id:
            extracted, _ = extract_command_line(comment.body or "", context.cmsbuild_user)
            first_line = extracted or first_line
            break

    try:
        result = parse_test_cmd(first_line)
    except TestCmdParseError as e:
        logger.warning(f"Invalid build/test command: {e}")
        context.messages.append(f"Invalid build/test command: {e}")
        return False

    # Collect for deferred processing
    context.pending_build_test_commands.append((result.verb, comment_id, user, timestamp, result))
    logger.debug(
        f"Collected {result.verb} command from {user} (comment {comment_id}) for deferred processing"
    )

    return True


def get_comment_reactions(context: PRContext, comment_id: int) -> List[str]:
    """
    Get list of reactions on a comment from the bot user.

    Args:
        context: PR processing context
        comment_id: Comment ID to check

    Returns:
        List of reaction types (e.g., ['+1', '-1']) from bot
    """
    if not context.cmsbuild_user:
        return []

    reactions = []
    for comment in context.comments:
        if comment.id == comment_id:
            # Check if comment object has reactions
            try:
                comment_reactions = comment.get_reactions()
                for reaction in comment_reactions:
                    if reaction.user.login == context.cmsbuild_user:
                        reactions.append(reaction.content)
            except Exception:
                pass
            break

    return reactions


def get_jenkins_status_url(context: PRContext) -> Optional[str]:
    """
    Get the URL from the bot/{prId}/jenkins commit status.

    Args:
        context: PR processing context

    Returns:
        URL from the status, or None if status doesn't exist
    """
    if not context.pr:
        return None

    pr_id = context.issue.number
    status_context = f"bot/{pr_id}/jenkins"

    try:
        head_sha = context.pr.head.sha
        repo = context.repo
        commit = repo.get_commit(head_sha)

        for status in commit.get_statuses():
            if status.context == status_context:
                return status.target_url
    except Exception as e:
        logger.debug(f"Error getting jenkins status: {e}")

    return None


def get_comment_url(context: PRContext, comment_id: int) -> str:
    """
    Get the URL for a comment.

    Args:
        context: PR processing context
        comment_id: Comment ID

    Returns:
        Comment URL
    """
    # GitHub comment URL format: https://github.com/{owner}/{repo}/pull/{pr_number}#issuecomment-{comment_id}
    repo_name = context.repo_name
    repo_org = context.repo_org
    pr_number = context.issue.number

    return f"https://github.com/{repo_org}/{repo_name}/pull/{pr_number}#issuecomment-{comment_id}"


def process_pending_build_test_commands(context: PRContext) -> None:
    """
    Process collected build/test commands after all comments have been seen.

    Rules:
    - For 'test': Last one wins (only process the last test command)
    - For 'build': Skip if comment already has +1 reaction from bot
    - For 'test': Skip if bot/{prId}/jenkins status exists and URL matches comment URL
    """
    if not context.pending_build_test_commands:
        return

    # Separate build and test commands
    build_commands = []
    test_commands = []

    for verb, comment_id, user, timestamp, result in context.pending_build_test_commands:
        if verb == "build":
            build_commands.append((comment_id, user, timestamp, result))
        else:  # test
            test_commands.append((comment_id, user, timestamp, result))

    # Process build commands - each one individually, skip if has +1 from bot
    for comment_id, user, timestamp, result in build_commands:
        # Check if comment has +1 reaction from bot
        reactions = get_comment_reactions(context, comment_id)
        if "+1" in reactions:
            logger.info(f"Skipping build command (comment {comment_id}) - already has +1 from bot")
            continue

        _execute_build_test_command(context, comment_id, user, result)

    # Process test commands - only the last one
    if test_commands:
        # Get jenkins status URL
        jenkins_url = get_jenkins_status_url(context)

        # Process only the last test command
        comment_id, user, timestamp, result = test_commands[-1]
        comment_url = get_comment_url(context, comment_id)

        # Check if jenkins status URL matches this comment's URL
        if jenkins_url:
            if jenkins_url == comment_url:
                logger.info(
                    f"Skipping test command (comment {comment_id}) - jenkins status already set for this comment"
                )
                return

        # Execute the test command
        if _execute_build_test_command(context, comment_id, user, result):
            # Update jenkins status URL to this comment's URL
            set_jenkins_status_url(context, comment_url)


def set_jenkins_status_url(context: PRContext, url: str) -> bool:
    """
    Set the bot/{prId}/jenkins commit status with the given URL.

    This is used to track which test command comment triggered the current test,
    so we don't re-trigger the same test on subsequent runs.

    Args:
        context: PR processing context
        url: URL to set as the status target_url (typically the comment URL)

    Returns:
        True if status was set successfully
    """
    if not context.pr:
        return False

    if context.dry_run:
        logger.info(f"[DRY RUN] Would set jenkins status URL to: {url}")
        return True

    pr_id = context.issue.number
    status_context = f"bot/{pr_id}/jenkins"

    try:
        head_sha = context.pr.head.sha
        repo = context.repo
        commit = repo.get_commit(head_sha)

        commit.create_status(
            state="pending",
            target_url=url,
            description="Test triggered",
            context=status_context,
        )
        logger.info(f"Set jenkins status URL to: {url}")
        return True
    except Exception as e:
        logger.error(f"Error setting jenkins status: {e}")
        return False


def _execute_build_test_command(
    context: PRContext, comment_id: int, user: str, result: "TestCmdResult"
) -> bool:
    """
    Execute a build/test command (internal helper).

    Args:
        context: PR processing context
        comment_id: Comment ID that triggered this
        user: User who triggered the command
        result: Parsed test command result

    Returns:
        True if command was executed successfully
    """
    # Check if required signatures (PRE_CHECKS) are present
    signing_checks = context.get_signing_checks_for_pr()
    required_categories = signing_checks.pre_checks
    if required_categories:
        category_states = compute_category_approval_states(context)
        missing_signatures = []

        for cat in required_categories:
            state = category_states.get(cat, ApprovalState.PENDING)
            if state != ApprovalState.APPROVED:
                missing_signatures.append(cat)

        if missing_signatures:
            msg = f"Cannot trigger {result.verb}: missing required signatures for {', '.join(missing_signatures)}"
            logger.info(msg)
            context.messages.append(msg)
            return False

    # Start with defaults from 'test parameters:' command
    # Command values override test_params values
    workflows = result.workflows if result.workflows else []
    prs = result.prs if result.prs else []
    queue = result.queue or ""
    build_full = bool(result.full)
    extra_packages = result.addpkg if result.addpkg else []

    # Apply test_params as defaults (only if not specified in command)
    if context.test_params:
        if not workflows and "WORKFLOWS" in context.test_params:
            workflows = context.test_params["WORKFLOWS"].split(",")
        if not prs and "PULL_REQUESTS" in context.test_params:
            prs = context.test_params["PULL_REQUESTS"].split(",")
        if not queue and "RELEASE_FORMAT" in context.test_params:
            queue = context.test_params["RELEASE_FORMAT"]
        if not extra_packages and "EXTRA_PACKAGES" in context.test_params:
            extra_packages = context.test_params["EXTRA_PACKAGES"].split(",")
        # Note: build_full from command always takes precedence

    # Create test request
    request = TestRequest(
        verb=result.verb,
        workflows=",".join(sorted(set(workflows))) if workflows else "",
        prs=sorted(prs) if prs else [],
        queue=queue,
        build_full=build_full,
        extra_packages=",".join(sorted(set(extra_packages))) if extra_packages else "",
        triggered_by=user,
        comment_id=comment_id,
    )

    # Check for duplicate test (same parameters)
    existing_keys = {t.test_key for t in context.tests_to_run}
    if request.test_key in existing_keys:
        logger.info(f"Duplicate test request ignored: {request.test_key}")
        return True  # Still return True as the command was valid

    context.tests_to_run.append(request)
    logger.info(f"{result.verb.capitalize()} triggered by {user}: {request}")

    return True


# =============================================================================
# FILE STATE MANAGEMENT
# =============================================================================


def get_pr_files_info(pr) -> Tuple[Dict[str, str], List[str]]:
    """
    Get all files in the PR with their blob SHAs and changed file list.

    Fetches pr.get_files() once and returns both:
    - Dict mapping filename to blob_sha (for files with SHAs)
    - List of changed filenames including previous filenames for renames

    Returns:
        Tuple of (files_with_sha, changed_files_list)
    """
    files = {}
    changed_files = []
    for f in pr.get_files():
        # For deleted files, sha might be None
        if f.sha:
            files[f.filename] = f.sha
        changed_files.append(f.filename)
        # Include previous filename for renamed files
        if f.previous_filename:
            changed_files.append(f.previous_filename)
    return files, changed_files


def get_pr_files(pr) -> Dict[str, str]:
    """
    Get all files in the PR with their blob SHAs.

    Returns:
        Dict mapping filename to blob_sha
    """
    files, _ = get_pr_files_info(pr)
    return files


def get_changed_files(pr) -> List[str]:
    """
    Get list of changed file names in a PR.

    Includes the previous filename for renamed files.

    Args:
        pr: Pull request object

    Returns:
        List of changed file paths (including old names for renames)
    """
    _, changed_files = get_pr_files_info(pr)
    return changed_files


def update_file_states(context: PRContext) -> Tuple[Set[str], Set[str]]:
    """
    Update file states based on current PR state.

    Updates current_file_versions in cache with the current file version keys.

    Returns:
        Tuple of (changed_files, new_categories):
        - changed_files: Set of filenames that changed since last check
        - new_categories: Set of categories that are new (not seen before in this PR)
    """
    # Use cached files if available, otherwise fetch
    if context._pr_files_with_sha is not None:
        current_files = context._pr_files_with_sha
    else:
        current_files = get_pr_files(context.pr)
    changed_files = set()
    new_categories = set()
    now = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")

    # Get commit timestamp from cached commits
    if context.commits:
        last_commit = context.commits[-1]
        try:
            commit_ts = last_commit.commit.author.date
            if isinstance(commit_ts, datetime):
                # Ensure tz-aware before formatting
                commit_ts = ensure_tz_aware(commit_ts)
                now = commit_ts.isoformat().replace("+00:00", "Z")
            elif commit_ts:
                # String timestamp
                now = str(commit_ts)
        except Exception:
            pass

    # Get old file version keys for comparison
    old_fv_keys = set(context.cache.current_file_versions)

    # Get categories that were already known before this update
    old_categories = set()
    for fv_key in old_fv_keys:
        if fv_key in context.cache.file_versions:
            old_categories.update(context.cache.file_versions[fv_key].categories)

    # Build list of current file version keys
    current_fv_keys = []

    for filename, blob_sha in current_files.items():
        fv_key = f"{filename}::{blob_sha}"
        current_fv_keys.append(fv_key)

        if fv_key not in context.cache.file_versions:
            # New file version - recalculate categories
            categories = get_file_l2_categories(
                context.repo_config, filename, datetime.now(tz=timezone.utc)
            )
            context.cache.file_versions[fv_key] = FileVersion(
                filename=filename,
                blob_sha=blob_sha,
                timestamp=now,
                categories=categories,
            )
            changed_files.add(filename)

            # Track categories that are new to this PR
            for cat in categories:
                if cat not in old_categories:
                    new_categories.add(cat)

    # Check for files that were removed
    old_filenames = set()
    for fv_key in old_fv_keys:
        if "::" in fv_key:
            filename = fv_key.split("::")[0]
            old_filenames.add(filename)

    for filename in old_filenames:
        if filename not in current_files:
            changed_files.add(filename)

    # Update current file versions
    context.cache.current_file_versions = current_fv_keys
    logger.debug(
        f"Updated file states: {len(current_fv_keys)} files, {len(changed_files)} changed, {len(new_categories)} new categories"
    )

    return changed_files, new_categories


# =============================================================================
# REACTION MANAGEMENT
# =============================================================================


def set_comment_reaction(
    context: PRContext,
    comment,
    comment_id: int,
    success: bool,
) -> None:
    """
    Set reaction on a comment based on command success.

    Uses cache to avoid redundant API calls.

    Args:
        context: PR processing context
        comment: The comment object
        comment_id: Comment ID
        success: True for +1 reaction, False for -1 reaction
    """
    desired_reaction = REACTION_PLUS_ONE if success else REACTION_MINUS_ONE
    cached_reaction = context.cache.get_cached_reaction(comment_id)

    # If reaction already matches, no action needed
    if cached_reaction == desired_reaction:
        logger.debug(f"Comment {comment_id} already has {desired_reaction} reaction (cached)")
        return

    # Need to update reaction
    if context.dry_run:
        logger.info(f"[DRY RUN] Would set {desired_reaction} reaction on comment {comment_id}")
    else:
        try:
            # Remove old reaction if different
            if cached_reaction:
                try:
                    # PyGithub API for removing reactions
                    for reaction in comment.get_reactions():
                        if (
                            reaction.user.login == context.cmsbuild_user
                            and reaction.content == cached_reaction
                        ):
                            reaction.delete()
                            break
                except Exception as e:
                    logger.warning(f"Failed to remove old reaction: {e}")

            # Add new reaction
            comment.create_reaction(desired_reaction)
            logger.debug(f"Set {desired_reaction} reaction on comment {comment_id}")

        except Exception as e:
            logger.warning(f"Failed to set reaction on comment {comment_id}: {e}")
            return

    # Update cache
    context.cache.set_reaction(comment_id, desired_reaction)


# =============================================================================
# COMMENT PROCESSING
# =============================================================================


def ensure_tz_aware(dt: datetime) -> datetime:
    """
    Ensure a datetime object is timezone-aware (UTC).

    PyGithub 1.56 returns tz-naive datetimes that are actually UTC.
    This function adds UTC timezone info to naive datetimes.

    Args:
        dt: A datetime object (may be naive or aware)

    Returns:
        Timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's UTC (as GitHub always returns Zulu time)
        return dt.replace(tzinfo=timezone.utc)
    return dt


def parse_timestamp(ts: str) -> Optional[datetime]:
    """
    Parse an ISO format timestamp string to timezone-aware datetime.

    Always returns UTC timezone-aware datetime.
    """
    if not ts:
        return None
    try:
        # Handle various ISO formats
        ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return ensure_tz_aware(dt)
    except ValueError:
        return None


def get_comment_timestamp(comment) -> datetime:
    """
    Get the timestamp of a comment as timezone-aware datetime.

    PyGithub 1.56 returns naive datetimes that are actually UTC.
    """
    ts = comment.created_at
    if isinstance(ts, datetime):
        return ensure_tz_aware(ts)
    # If it's a string, parse it
    parsed = parse_timestamp(str(ts))
    return parsed if parsed else datetime.now(tz=timezone.utc)


def check_command_acl(
    context: PRContext, command: Command, user: str, timestamp: datetime
) -> bool:
    """Check if user has permission to run a command."""
    if command.acl is None:
        return True

    if callable(command.acl):
        return command.acl(context, user, timestamp)

    # acl is an Iterable[str] - check if user is in allowlist or has required L2 membership
    acl_items = list(command.acl)  # Convert to list for iteration
    if user in acl_items:
        return True

    # Check if user has required L2 membership
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)
    for required in acl_items:
        if required in user_categories:
            return True

    return False


def get_latest_commit_timestamp(context: PRContext) -> Optional[datetime]:
    """
    Get the timestamp of the latest (most recent) commit in the PR.

    Returns:
        Timestamp of latest commit, or None if no commits
    """
    if not context.commits:
        return None

    latest_ts = None
    for commit in context.commits:
        try:
            commit_date = commit.commit.author.date
            if commit_date:
                ts = (
                    ensure_tz_aware(commit_date)
                    if isinstance(commit_date, datetime)
                    else parse_timestamp(commit_date)
                )
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts
        except Exception:
            pass

    return latest_ts


def is_bot_command_reset_on_push(command_line: str) -> bool:
    """
    Check if a command is a bot command that resets on push.

    These are signatures posted by the bot itself (+1, -1, +code-checks, -code-checks).
    """
    if not command_line:
        return False

    for pattern in BOT_COMMANDS_RESET_ON_PUSH:
        if re.match(pattern, command_line, re.IGNORECASE):
            return True
    return False


def should_skip_command_before_latest_commit(
    context: PRContext,
    command: Command,
    command_line: str,
    comment_timestamp: datetime,
    is_bot_comment: bool,
) -> bool:
    """
    Check if a command should be skipped because it's before the latest commit.

    Commands with reset_on_push=True, and bot signatures (code-checks, +1/-1)
    should only apply to the current code state.

    Args:
        context: PR processing context
        command: The command being executed
        command_line: The command line text
        comment_timestamp: When the comment was created
        is_bot_comment: Whether the comment is from the bot

    Returns:
        True if command should be skipped
    """
    if not context.is_pr:
        return False

    latest_commit_ts = get_latest_commit_timestamp(context)
    if latest_commit_ts is None:
        return False

    # Check if comment is before latest commit
    if comment_timestamp >= latest_commit_ts:
        return False  # Comment is after latest commit, don't skip

    # Check if this command has reset_on_push property set
    if command.reset_on_push:
        logger.debug(f"Skipping command '{command.name}' - comment is before latest commit")
        return True

    # Check if this is a bot command that resets on push
    if is_bot_comment and is_bot_command_reset_on_push(command_line):
        logger.debug(f"Skipping bot command '{command_line}' - comment is before latest commit")
        return True

    return False


def process_comment(context: PRContext, comment) -> None:
    """
    Process a single comment for commands.

    Iterates through all matching commands until one returns True (success)
    or False (explicit failure). If a handler returns None, the next matching
    command is tried (fallthrough).
    """
    # Skip already processed comments
    if str(comment.id) in context.cache.comments:
        return

    command_line, bot_mentioned = extract_command_line(comment.body or "", context.cmsbuild_user)
    if not command_line:
        return

    user = comment.user.login
    timestamp = get_comment_timestamp(comment)
    comment_id = comment.id
    is_bot = context.cmsbuild_user and user == context.cmsbuild_user

    # Try each matching command until one handles it (returns True or False)
    command_handled = False
    for cmd, match in context.command_registry.find_commands(command_line, is_pr=context.is_pr):
        # Check if command should be skipped because it's before the latest commit
        if should_skip_command_before_latest_commit(context, cmd, command_line, timestamp, is_bot):
            # Cache the comment as processed (locked) but don't execute
            # This prevents re-processing on subsequent runs
            context.cache.comments[str(comment_id)] = CommentInfo(
                timestamp=timestamp.isoformat() if timestamp else "",
                first_line=command_line,
                ctype=cmd.name,
                user=user,
                locked=True,  # Mark as locked so it won't be re-processed
            )
            logger.debug(f"Cached skipped command '{cmd.name}' from comment {comment_id}")
            command_handled = True
            break

        # Check ACL
        if not check_command_acl(context, cmd, user, timestamp):
            logger.info(f"User {user} not authorized for command: {cmd.name}")
            # Set -1 reaction for unauthorized
            set_comment_reaction(context, comment, comment_id, success=False)
            command_handled = True
            break

        # Execute command - handler returns:
        #   True  = success (stop processing)
        #   False = failure (stop processing)
        #   None  = doesn't apply, try next command (fallthrough)
        logger.info(f"Trying command '{cmd.name}' from user {user}")
        try:
            result = cmd.handler(context, match, user, comment_id, timestamp)
        except Exception as e:
            logger.error(f"Command handler error: {e}")
            result = False

        if result is None:
            # Handler returned None - command doesn't apply, try next match
            logger.debug(f"Command '{cmd.name}' returned None, trying next match")
            continue

        # Command handled (success or failure)
        command_handled = True
        set_comment_reaction(context, comment, comment_id, success=result)
        break

    # If bot was mentioned but no command matched or handled, react with -1
    if not command_handled and bot_mentioned:
        logger.info(f"Bot mentioned but command not recognized: {command_line}")
        set_comment_reaction(context, comment, comment_id, success=False)


def get_commit_timestamps(context: PRContext) -> List[datetime]:
    """
    Get timestamps of all commits in the PR, sorted chronologically.

    Uses context.commits which should be populated before calling this function.
    All returned timestamps are timezone-aware (UTC).

    Returns:
        List of commit timestamps (timezone-aware datetime objects)
    """
    if not context.commits:
        return []

    timestamps = []
    for commit in context.commits:
        try:
            commit_date = commit.commit.author.date
            if commit_date:
                if isinstance(commit_date, datetime):
                    # PyGithub 1.56 returns naive datetimes - make them tz-aware
                    timestamps.append(ensure_tz_aware(commit_date))
                else:
                    # Parse string timestamp
                    parsed = parse_timestamp(commit_date)
                    if parsed:
                        timestamps.append(parsed)
        except Exception as e:
            logger.warning(f"Failed to get timestamp from commit: {e}")

    timestamps.sort()
    return timestamps


def has_commit_after(commit_timestamps: List[datetime], comment_timestamp: datetime) -> bool:
    """
    Check if there's a commit after the given comment timestamp.

    Args:
        commit_timestamps: Sorted list of commit timestamps
        comment_timestamp: Timestamp to check against

    Returns:
        True if any commit is after the comment timestamp
    """
    for commit_ts in commit_timestamps:
        if commit_ts > comment_timestamp:
            return True
    return False


def get_last_commit_before(
    commit_timestamps: List[datetime], timestamp: datetime
) -> Optional[datetime]:
    """
    Get the timestamp of the last commit before the given timestamp.

    Args:
        commit_timestamps: Sorted list of commit timestamps
        timestamp: Timestamp to check against

    Returns:
        Timestamp of the last commit before the given time, or None if no commits before
    """
    last_commit = None
    for commit_ts in commit_timestamps:
        if commit_ts <= timestamp:
            last_commit = commit_ts
        else:
            break
    return last_commit


def process_all_comments(context: PRContext) -> None:
    """
    Process all comments on the PR/Issue.

    This function handles:
    1. Locking signatures that have a commit after them
    2. Detecting deleted comments (remove from cache if not locked)
    3. Detecting edited comments (re-process if not locked)
    4. Processing new comments

    Uses context.comments which should be populated before calling this function.
    """
    # Use comments from context (already fetched once)
    current_comments = context.comments
    current_comment_ids = {str(c.id) for c in current_comments}

    # Get commit timestamps for locking logic (only for PRs)
    commit_timestamps = get_commit_timestamps(context) if context.is_pr else []

    # First pass: lock any signatures that have commits after them
    for comment_id, comment_info in context.cache.comments.items():
        if comment_info.locked:
            continue  # Already locked

        # Only lock signature commands (+1, -1)
        if comment_info.ctype not in ("+1", "-1"):
            continue

        comment_ts = parse_timestamp(comment_info.timestamp)
        if comment_ts and has_commit_after(commit_timestamps, comment_ts):
            comment_info.locked = True
            logger.debug(f"Locked signature in comment {comment_id} (commit after)")

    # Second pass: handle deleted comments
    deleted_comment_ids = []
    for comment_id in list(context.cache.comments.keys()):
        if comment_id not in current_comment_ids:
            comment_info = context.cache.comments[comment_id]
            if comment_info.locked:
                # Keep locked signatures even if comment is deleted
                logger.debug(f"Keeping locked signature from deleted comment {comment_id}")
            else:
                # Remove unlocked signature
                deleted_comment_ids.append(comment_id)
                logger.info(f"Removing signature from deleted comment {comment_id}")

    for comment_id in deleted_comment_ids:
        del context.cache.comments[comment_id]
        # Also remove reaction cache for deleted comment
        if comment_id in context.cache.emoji:
            del context.cache.emoji[comment_id]

    # Third pass: process current comments (sorted by ID for chronological order)
    sorted_comments = sorted(current_comments, key=lambda c: c.id)

    for comment in sorted_comments:
        comment_id = str(comment.id)
        cached_info = context.cache.comments.get(comment_id)

        if cached_info:
            if cached_info.locked:
                # Locked comment - don't re-process even if edited
                logger.debug(f"Skipping locked comment {comment_id}")
                continue

            # Check if comment was edited by comparing preprocessed first line
            current_first_line, _ = extract_command_line(comment.body or "", context.cmsbuild_user)
            current_first_line = current_first_line or ""
            if cached_info.first_line != current_first_line:
                # Comment was edited - remove old info and re-process
                logger.info(f"Comment {comment_id} was edited, re-processing")
                del context.cache.comments[comment_id]
                if comment_id in context.cache.emoji:
                    del context.cache.emoji[comment_id]
                # Fall through to process_comment
            else:
                # Comment unchanged, skip
                continue

        # Process the comment (new or edited)
        process_comment(context, comment)


# =============================================================================
# CATEGORY AND STATE COMPUTATION
# =============================================================================


def get_current_categories(context: PRContext) -> Dict[str, Set[str]]:
    """
    Get all categories and their associated file version keys from current PR state.

    Categories come from multiple sources:
    1. Automatic assignment: file → package → categories (stored in FileVersion.categories)
    2. Manual assignment: 'assign'/'unassign' commands (stored in context.signing_categories)
    3. PRE_CHECKS: Categories required before tests (from repo_config)
    4. EXTRA_CHECKS: Categories required for merge (from repo_config)

    Returns:
        Dict mapping category name to set of file version keys (filename::sha)
    """
    categories: Dict[str, Set[str]] = {}
    current_files = context.cache.current_file_versions

    if not current_files:
        return categories

    # Get categories from file versions (automatic assignment)
    for fv_key in current_files:
        if fv_key in context.cache.file_versions:
            fv = context.cache.file_versions[fv_key]
            for cat in fv.categories:
                if cat not in categories:
                    categories[cat] = set()
                categories[cat].add(fv_key)

    # Add manually assigned categories from context.signing_categories
    # (populated by assign/unassign command handlers during comment processing)
    for cat in context.signing_categories:
        if cat not in categories:
            categories[cat] = set()
        categories[cat].update(current_files)

    # Add PRE_CHECKS and EXTRA_CHECKS categories from get_signing_checks
    # These are required signatures that apply to all files
    signing_checks = context.get_signing_checks_for_pr()

    for cat in signing_checks.pre_checks + signing_checks.extra_checks:
        if cat not in categories:
            categories[cat] = set()
        # These categories apply to all files
        categories[cat].update(current_files)

    return categories


def get_files_for_categories(context: PRContext, categories: List[str]) -> List[str]:
    """
    Get current file version keys for the specified categories.

    When signing categories, this returns the files that the signature covers.
    The signature is valid only while these exact file versions are current.

    Args:
        context: PR processing context
        categories: List of category names being signed

    Returns:
        List of file version keys (filename::sha) for files in those categories
    """
    all_categories = get_current_categories(context)
    signed_files: Set[str] = set()

    for cat in categories:
        if cat in all_categories:
            signed_files.update(all_categories[cat])

    return sorted(signed_files)


def is_signature_valid_for_category(
    context: PRContext, comment_info: CommentInfo, category: str, current_category_files: Set[str]
) -> bool:
    """
    Check if a signature is still valid for a specific category.

    A signature for a category is valid if:
    1. All files that were signed are still current (haven't changed)
    2. All current files in the category were covered by the signature (no new files added)

    Args:
        context: PR processing context
        comment_info: The signature comment info
        category: The category to check
        current_category_files: Current file version keys for this category

    Returns:
        True if signature is still valid for this category, False otherwise
    """
    if not comment_info.signed_files:
        # No files recorded - signature is invalid (legacy or error)
        return False

    signed_files_set = set(comment_info.signed_files)
    current_files_set = set(context.cache.current_file_versions)

    # Check 1: All signed files for this category must still be current
    # (Filter to only files that belong to this category)
    for signed_file in signed_files_set:
        if signed_file not in current_files_set:
            # This file has changed since signing
            return False

    # Check 2: All current files in this category must have been signed
    # (No new files added to the category since signing)
    for current_file in current_category_files:
        if current_file not in signed_files_set:
            # New file added to category since signing
            return False

    return True


def compute_category_approval_states(context: PRContext) -> Dict[str, ApprovalState]:
    """
    Compute approval state for each category based on signatures.

    A signature for a category is valid only if:
    1. All files signed are still current (haven't changed)
    2. No new files have been added to the category since signing

    Special handling:
    - 'tests' category: Determined by CI commit statuses, not user comments
    - 'code-checks' category: Can be signed by CI or users

    Returns:
        Dict mapping category name to approval state
    """
    categories = get_current_categories(context)
    category_states: Dict[str, ApprovalState] = {}

    for cat_name, cat_files in categories.items():
        # Special handling for 'tests' category - determined by CI status
        if cat_name == "tests":
            category_states[cat_name] = _get_tests_approval_state(context)
            continue

        # Find valid signatures for this category from comments
        approved = False
        rejected = False

        for comment_id, comment_info in context.cache.comments.items():
            if comment_info.ctype not in ("+1", "-1"):
                continue
            if cat_name not in comment_info.categories:
                continue
            if not is_signature_valid_for_category(context, comment_info, cat_name, cat_files):
                continue

            if comment_info.ctype == "+1":
                approved = True
            elif comment_info.ctype == "-1":
                rejected = True

        if rejected:
            category_states[cat_name] = ApprovalState.REJECTED
        elif approved:
            category_states[cat_name] = ApprovalState.APPROVED
        else:
            category_states[cat_name] = ApprovalState.PENDING

    return category_states


def _get_tests_approval_state(context: PRContext) -> ApprovalState:
    """
    Get the approval state for the 'tests' category based on CI status.

    The tests category is special - it's determined by GitHub commit statuses
    from Jenkins CI, not by user comments.

    Logic:
    1. Check for required test statuses first
    2. If no required tests, check optional tests
    3. Map CI status to approval state:
       - All success -> APPROVED
       - Any error (on required) -> REJECTED
       - Any pending or no tests -> PENDING

    Returns:
        ApprovalState for the tests category
    """
    lab_stats = check_ci_test_completion(context)

    if not lab_stats:
        # No test results yet - still pending
        return ApprovalState.PENDING

    # Check required tests first (they take precedence)
    if "required" in lab_stats:
        required_status = lab_stats["required"]
        if required_status == "success":
            return ApprovalState.APPROVED
        elif required_status == "error":
            # Check if test failures are being ignored
            if context.ignore_tests_rejected:
                return ApprovalState.APPROVED
            return ApprovalState.REJECTED

    # Fall back to optional tests if no required tests
    if "optional" in lab_stats:
        optional_status = lab_stats["optional"]
        if optional_status == "success":
            return ApprovalState.APPROVED
        # Optional test errors don't cause rejection, just stay pending
        # (unless we want different behavior)
        return ApprovalState.PENDING

    return ApprovalState.PENDING


def determine_pr_state(context: PRContext) -> PRState:
    """
    Determine the current PR state.

    1. If merged -> merged
    2. If any PRE_CHECKS pending/rejected -> tests-pending
    3. If any EXTRA_CHECKS (except orp) pending/rejected -> signatures-pending
    4. Else -> fully-signed
    """
    # Check if already merged
    if context.pr and context.pr.merged:
        return PRState.MERGED

    category_states = compute_category_approval_states(context)

    # Get required checks
    signing_checks = context.get_signing_checks_for_pr()
    pre_checks = signing_checks.pre_checks
    extra_checks = signing_checks.extra_checks

    # Check PRE_CHECKS first (code-checks, etc.)
    for cat in pre_checks:
        state = category_states.get(cat, ApprovalState.PENDING)
        if state != ApprovalState.APPROVED:
            return PRState.TESTS_PENDING

    # Check EXTRA_CHECKS (tests, orp, etc.) - but ORP is special
    for cat in extra_checks:
        if cat.lower() == "orp":
            continue  # ORP is checked separately in can_merge
        state = category_states.get(cat, ApprovalState.PENDING)
        if state != ApprovalState.APPROVED:
            return PRState.SIGNATURES_PENDING

    # Check all other categories from file ownership
    for cat_name, state in category_states.items():
        # Skip categories we already checked
        if cat_name in pre_checks or cat_name in extra_checks:
            continue
        if state != ApprovalState.APPROVED:
            return PRState.SIGNATURES_PENDING

    return PRState.FULLY_SIGNED


def can_merge(context: PRContext) -> bool:
    """
    Check if PR can be merged.

    Conditions:
    1. PR state is fully-signed
    2. No active holds
    3. ORP approved (if in EXTRA_CHECKS)
    """
    if not context.is_pr:
        return False

    pr_state = determine_pr_state(context)

    if pr_state != PRState.FULLY_SIGNED:
        return False

    if context.holds:
        return False

    # Check if ORP is required (in EXTRA_CHECKS)
    signing_checks = context.get_signing_checks_for_pr()
    extra_checks = signing_checks.extra_checks

    if "orp" in [c.lower() for c in extra_checks]:
        category_states = compute_category_approval_states(context)
        orp_state = category_states.get("orp", ApprovalState.PENDING)
        if orp_state != ApprovalState.APPROVED:
            return False

    return True


# =============================================================================
# STATUS REPORTING
# =============================================================================


# CI Status prefix for commit statuses
CMS_STATUS_PREFIX = "cms"


@dataclass
class CITestResult:
    """Result of CI test status check."""

    status: str  # "pending", "success", "error"
    is_optional: bool
    context: str  # Full status context
    description: str
    target_url: Optional[str] = None


def get_ci_test_statuses(context: PRContext) -> Dict[str, List[CITestResult]]:
    """
    Get CI test statuses from GitHub commit statuses.

    Looks for top-level statuses matching patterns:
    - cms/<pr_id>[/<flavor>]/<arch>/required
    - cms/<pr_id>[/<flavor>]/<arch>/optional

    The <flavor> component is optional and omitted when flavor is DEFAULT.

    Examples:
    - cms/10246/el8_amd64_gcc13/required (default flavor, omitted)
    - cms/10246/el8_amd64_gcc13/optional
    - cms/10246/ROOT638/el8_amd64_gcc13/required (with flavor)
    - cms/10246/ROOT638/el8_amd64_gcc13/optional

    And their sub-statuses for determining overall status:
    - cms/<pr_id>[/<flavor>]/<arch>/build
    - cms/<pr_id>[/<flavor>]/<arch>/relvals
    - etc.

    Returns:
        Dict mapping suffix ("required" or "optional") to list of CITestResult
    """
    if not context.pr or not context.commits:
        return {}

    # Get the head commit SHA
    try:
        head_sha = context.pr.head.sha
    except Exception:
        if context.commits:
            head_sha = context.commits[-1].sha
        else:
            return {}

    # Get commit statuses
    try:
        commit = context.repo.get_commit(head_sha)
        statuses = list(commit.get_statuses())
    except Exception as e:
        logger.warning(f"Failed to get commit statuses: {e}")
        return {}

    if not statuses:
        return {}

    # Group statuses by their context prefix
    # Build a map of context -> status for quick lookup
    status_map: Dict[str, Any] = {}
    for status in statuses:
        ctx = status.context
        # Keep the most recent status for each context
        if ctx not in status_map:
            status_map[ctx] = status

    results: Dict[str, List[CITestResult]] = {"required": [], "optional": []}

    # Find all top-level test statuses (cms/<arch>/<test>/required or optional)
    prefix = f"{CMS_STATUS_PREFIX}/"

    for ctx, status in status_map.items():
        if not ctx.startswith(prefix):
            continue

        # Check if this is a top-level status (ends with /required or /optional)
        parts = ctx.rsplit("/", 1)
        if len(parts) != 2:
            continue

        base_context, suffix = parts
        if suffix not in ("required", "optional"):
            continue

        # This is a top-level test status
        # Determine overall status by checking sub-statuses
        overall_status = _compute_test_status(base_context, status_map)

        result = CITestResult(
            status=overall_status,
            is_optional=(suffix == "optional"),
            context=ctx,
            description=status.description or "",
            target_url=status.target_url,
        )
        results[suffix].append(result)

    return results


def _compute_test_status(base_context: str, status_map: Dict[str, Any]) -> str:
    """
    Compute the overall status for a test by checking its sub-statuses.

    Args:
        base_context: The base context, e.g.:
            - "cms/10246/el8_amd64_gcc13" (default flavor)
            - "cms/10246/ROOT638/el8_amd64_gcc13" (with flavor)
        status_map: Map of context -> status object

    Returns:
        "pending", "success", or "error"
    """
    # Find all sub-statuses for this base context
    sub_statuses = []
    prefix = f"{base_context}/"

    for ctx, status in status_map.items():
        if ctx.startswith(prefix) or ctx == base_context:
            sub_statuses.append(status)

    if not sub_statuses:
        # No sub-statuses, check the main status
        if base_context in status_map:
            main_status = status_map[base_context]
            return _github_state_to_status(main_status.state)
        return "pending"

    # Check all sub-statuses
    has_pending = False
    has_error = False

    for status in sub_statuses:
        state = (
            status.state.lower() if hasattr(status.state, "lower") else str(status.state).lower()
        )
        if state == "pending":
            has_pending = True
        elif state in ("error", "failure"):
            has_error = True

    if has_pending:
        return "pending"
    if has_error:
        return "error"
    return "success"


def _github_state_to_status(state: str) -> str:
    """Convert GitHub status state to our status string."""
    state = state.lower() if hasattr(state, "lower") else str(state).lower()
    if state == "pending":
        return "pending"
    elif state in ("error", "failure"):
        return "error"
    elif state == "success":
        return "success"
    return "pending"


def check_ci_test_completion(context: PRContext) -> Optional[Dict[str, str]]:
    """
    Check if CI tests have completed and return their results.

    Returns:
        Dict with keys "required" and/or "optional" mapping to "success" or "error",
        or None if tests are still pending or not found.
    """
    statuses = get_ci_test_statuses(context)

    required_results = statuses.get("required", [])
    optional_results = statuses.get("optional", [])

    if not required_results and not optional_results:
        return None

    lab_stats: Dict[str, str] = {}

    # Check required tests
    if required_results:
        all_success = True
        any_error = False
        any_pending = False

        for result in required_results:
            if result.status == "pending":
                any_pending = True
            elif result.status == "error":
                any_error = True
                all_success = False
            elif result.status != "success":
                all_success = False

        if not any_pending:
            lab_stats["required"] = "success" if all_success and not any_error else "error"

    # Check optional tests
    if optional_results:
        all_success = True
        any_pending = False

        for result in optional_results:
            if result.status == "pending":
                any_pending = True
            elif result.status != "success":
                all_success = False

        if not any_pending:
            # Optional tests don't cause error state, just track success
            lab_stats["optional"] = "success" if all_success else "error"

    return lab_stats if lab_stats else None


def fetch_pr_result(url: str) -> Tuple[int, str]:
    """
    Fetch PR test result from Jenkins artifacts URL.

    Args:
        url: URL to fetch results from

    Returns:
        Tuple of (error_code, output_string)
        error_code is 0 on success, non-zero on failure
    """
    e, o = run_cmd("curl -k -s -L --max-time 60 %s" % url)
    return e, o


def process_ci_test_results(context: PRContext) -> None:
    """
    Process CI test results and post completion comments.

    Checks if tests have completed, fetches results from Jenkins,
    and posts +1/-1 comments based on test outcomes.
    """
    if not context.is_pr or not context.pr:
        return

    lab_stats = check_ci_test_completion(context)
    if not lab_stats:
        return

    statuses = get_ci_test_statuses(context)

    # Get current commit SHA for unique message key
    head_sha = context.pr.head.sha[:8] if context.pr else "unknown"

    for suffix, status_value in lab_stats.items():
        # Find a result with a target URL to fetch detailed results
        result_url = None
        for result in statuses.get(suffix, []):
            if result.target_url and result.status != "pending":
                # Check if description indicates completion
                if result.description and not result.description.startswith("Finished"):
                    result_url = result.target_url
                    break

        if not result_url:
            continue

        # Transform URL to get pr-result endpoint
        pr_result_url = (
            result_url.replace(
                "/SDT/jenkins-artifacts/",
                "/SDT/cgi-bin/get_pr_results/jenkins-artifacts/",
            )
            + "/pr-result"
        )

        error_code, output = fetch_pr_result(pr_result_url)

        if output:
            # Post result as comment using post_bot_comment for deduplication
            res = "+1" if status_value == "success" else "-1"
            comment_body = f"{res}\n\n{output}"

            # Use suffix and head_sha as message key to avoid duplicates
            message_key = f"ci_result_{suffix}_{head_sha}"
            post_bot_comment(context, comment_body, message_key)


def generate_status_message(context: PRContext) -> str:
    """Generate a status message for the PR or Issue."""
    lines = []
    entity_type = "PR" if context.is_pr else "Issue"
    pr_state = None

    if context.is_pr:
        pr_state = determine_pr_state(context)
        lines.append(f"**{entity_type} Status: {pr_state.value}**\n")
    else:
        lines.append(f"**{entity_type} Status**\n")

    # Category status (for PRs)
    if context.is_pr:
        category_states = compute_category_approval_states(context)
        signing_checks = context.get_signing_checks_for_pr()
        pre_checks = signing_checks.pre_checks
        extra_checks = signing_checks.extra_checks

        if category_states:
            lines.append("**Categories:**")
            for cat_name, state in sorted(category_states.items()):
                # Determine category type
                if cat_name in pre_checks:
                    type_str = "🔧"  # Pre-check (required for tests)
                elif cat_name in extra_checks:
                    type_str = "🔒"  # Extra check (required for merge)
                else:
                    type_str = "📌"  # Regular category
                state_emoji = {"approved": "✅", "rejected": "❌", "pending": "⏳"}[state.value]
                lines.append(f"- {type_str} {cat_name}: {state_emoji} {state.value}")

        # Holds
        if context.holds:
            lines.append("\n**Active Holds:**")
            for hold in context.holds:
                lines.append(f"- {hold.category} by @{hold.user}")

        # Merge status
        lines.append("")
        if can_merge(context):
            lines.append("✅ **Ready to merge**")
        else:
            reasons = []
            if pr_state == PRState.TESTS_PENDING:
                pending_pre = [
                    cat
                    for cat in pre_checks
                    if category_states.get(cat, ApprovalState.PENDING) != ApprovalState.APPROVED
                ]
                if pending_pre:
                    reasons.append(f"Pre-checks pending: {', '.join(pending_pre)}")
                else:
                    reasons.append("Tests not passed")
            elif pr_state == PRState.SIGNATURES_PENDING:
                pending_cats = [
                    cat
                    for cat, state in category_states.items()
                    if state != ApprovalState.APPROVED and cat.lower() != "orp"
                ]
                if pending_cats:
                    reasons.append(f"Pending signatures: {', '.join(pending_cats)}")
            if context.holds:
                reasons.append("Has active holds")

            # Check ORP
            if "orp" in [c.lower() for c in extra_checks]:
                orp_state = category_states.get("orp", ApprovalState.PENDING)
                if orp_state != ApprovalState.APPROVED:
                    reasons.append("ORP approval required")

            lines.append("❌ **Not ready to merge:**")
            for reason in reasons:
                lines.append(f"  - {reason}")

    # Labels section (for both PRs and Issues)
    all_labels = set(context.pending_labels)

    if all_labels:
        lines.append("\n**Labels:**")
        for label in sorted(all_labels):
            lines.append(f"- {label}")

    return "\n".join(lines)


def update_pr_status(context: PRContext) -> Tuple[Set[str], Set[str]]:
    """
    Update PR/Issue labels and status based on current state.

    Returns:
        Tuple of (old_labels, new_labels) for tracking state transitions
    """
    # Get current labels (old labels)
    old_labels = {label.name for label in context.issue.get_labels()}
    new_labels: Set[str] = set()
    labels_to_add: Set[str] = set()
    labels_to_remove: Set[str] = set()

    # Handle PR-specific state labels
    if context.is_pr:
        pr_state = determine_pr_state(context)

        state_labels = {
            PRState.TESTS_PENDING: "tests-pending",
            PRState.SIGNATURES_PENDING: "signatures-pending",
            PRState.FULLY_SIGNED: "fully-signed",
            PRState.MERGED: "merged",
        }

        # Compute new state labels
        for state, label in state_labels.items():
            if state == pr_state:
                new_labels.add(label)
                if label not in old_labels:
                    labels_to_add.add(label)
            else:
                if label in old_labels:
                    labels_to_remove.add(label)

        # Handle draft PR - use fully-signed-draft instead of fully-signed
        if context.is_draft and pr_state == PRState.FULLY_SIGNED:
            new_labels.discard("fully-signed")
            new_labels.add("fully-signed-draft")
            labels_to_add.discard("fully-signed")
            labels_to_add.add("fully-signed-draft")
            if "fully-signed-draft" in old_labels:
                labels_to_add.discard("fully-signed-draft")

        # Handle category state labels (<cat>-pending, <cat>-approved, <cat>-rejected)
        category_states = compute_category_approval_states(context)
        state_suffixes = {
            ApprovalState.PENDING: "-pending",
            ApprovalState.APPROVED: "-approved",
            ApprovalState.REJECTED: "-rejected",
        }

        for cat, state in category_states.items():
            # Add current state label
            current_state_label = f"{cat}{state_suffixes[state]}"
            new_labels.add(current_state_label)
            if current_state_label not in old_labels:
                labels_to_add.add(current_state_label)

            # Remove other state labels for this category
            for other_state, suffix in state_suffixes.items():
                if other_state != state:
                    old_label = f"{cat}{suffix}"
                    if old_label in old_labels:
                        labels_to_remove.add(old_label)

        # Add auto-labels based on file patterns
        auto_labels = get_labels_for_pr(context)
        for label in auto_labels:
            new_labels.add(label)
            if label not in old_labels:
                labels_to_add.add(label)

    # Handle type labels from 'type' command (works for both PRs and Issues)
    # First, handle 'type' labels (only one allowed) - remove old ones
    for label in old_labels:
        if label in TYPE_COMMANDS:
            label_info = TYPE_COMMANDS[label]
            label_type = label_info[2] if len(label_info) > 2 else "mtype"
            if label_type == "type" and label not in context.pending_labels:
                # Check if we're adding a new 'type' label
                adding_type_label = any(
                    l in context.pending_labels
                    and len(TYPE_COMMANDS.get(l, [])) > 2
                    and TYPE_COMMANDS[l][2] == "type"
                    for l in context.pending_labels
                )
                if adding_type_label:
                    labels_to_remove.add(label)

    # Add pending labels
    for label in context.pending_labels:
        new_labels.add(label)
        if label not in old_labels:
            labels_to_add.add(label)

    # Keep labels that aren't being removed
    for label in old_labels:
        if label not in labels_to_remove:
            new_labels.add(label)

    if context.dry_run:
        if labels_to_add:
            logger.info(f"[DRY RUN] Would add labels: {sorted(labels_to_add)}")
        if labels_to_remove:
            logger.info(f"[DRY RUN] Would remove labels: {sorted(labels_to_remove)}")
        return old_labels, new_labels

    # Log label changes
    if labels_to_add:
        logger.info(f"Adding labels: {sorted(labels_to_add)}")
    if labels_to_remove:
        logger.info(f"Removing labels: {sorted(labels_to_remove)}")

    # Apply label changes
    for label in labels_to_remove:
        try:
            context.issue.remove_from_labels(label)
            logger.debug(f"Removed label: {label}")
        except Exception as e:
            logger.warning(f"Could not remove label {label}: {e}")

    for label in labels_to_add:
        try:
            context.issue.add_to_labels(label)
            logger.debug(f"Added label: {label}")
        except Exception as e:
            logger.warning(f"Could not add label {label}: {e}")

    return old_labels, new_labels


def get_fully_signed_message(context: PRContext) -> str:
    """
    Generate the fully signed message for a PR.

    Returns the message to post when a PR becomes fully signed.
    """
    pr = context.pr
    branch = pr.base.ref if pr else "unknown"

    # Determine test status message
    requires_test = ""
    lab_stats = check_ci_test_completion(context)

    if lab_stats:
        required_status = lab_stats.get("required")
        if required_status == "success":
            requires_test = " (tests are also fine)"
        elif required_status == "error":
            if context.ignore_tests_rejected:
                requires_test = " (test failures were overridden)"
            else:
                requires_test = " (but tests are reportedly failing)"
    else:
        # Tests not completed yet
        requires_test = " after it passes the integration tests"

    # Check if this is a production branch that requires devel release validation
    dev_release_relval = ""
    if branch in RELEASE_BRANCH_PRODUCTION:
        dev_release_relval = f" and once validation in the development release cycle {CMSSW_DEVEL_BRANCH} is complete"

    # Determine auto-merge message
    auto_merge_msg = ""
    managers = get_release_managers(branch)
    managers_str = (
        ", ".join(format_mention(context, m) for m in managers)
        if managers
        else "@cms-sw/release-managers"
    )

    if context.holds:
        # PR is on hold
        blockers = ", ".join(format_mention(context, h.user) for h in context.holds)
        auto_merge_msg = (
            f"This PR is put on hold by {blockers}. They have to unhold to remove the hold state "
            f"or {managers_str} will have to merge it by hand."
        )
    elif has_new_package(context):
        # PR introduces new package
        auto_merge_msg = (
            f"This pull request requires a new package and will not be merged. {managers_str}"
        )
    elif needs_orp_review(context, branch):
        # PR needs ORP review
        auto_merge_msg = (
            f"This pull request will now be reviewed by the release team before it's merged. "
            f"{managers_str} (and backports should be raised in the release meeting by the corresponding L2)"
        )
    else:
        # Can be auto-merged
        auto_merge_msg = "This pull request will be automatically merged."

    # Build the message
    message = (
        f"This pull request is fully signed and it will be integrated in one of the next "
        f"{branch} IBs{requires_test}{dev_release_relval}. {auto_merge_msg}"
    )

    # Add notice about linked PRs if any
    linked_prs = get_linked_prs(context)
    if linked_prs:
        linked_prs_str = ", ".join(linked_prs)
        message += (
            f"\n\n**Notice** This PR was tested with additional Pull Request(s), "
            f"please also merge them if necessary: {linked_prs_str}"
        )

    return message


def has_new_package(context: PRContext) -> bool:
    """Check if PR introduces a new package."""
    # Check if any file is in a package that doesn't exist yet
    if not context.pr:
        return False

    for fv_key in context.cache.current_file_versions:
        if fv_key in context.cache.file_versions:
            fv = context.cache.file_versions[fv_key]
            # Check if this is a new file in a new package
            if fv.filename and "/" in fv.filename:
                pkg = file_to_package(context.repo_config, fv.filename)
                if pkg and pkg not in context.packages:
                    # This could indicate a new package
                    # More sophisticated check would look at actual package existence
                    pass

    # For now, check pending labels for new-package indication
    return "new-package" in context.pending_labels


def needs_orp_review(context: PRContext, branch: str) -> bool:
    """Check if PR needs ORP (Operations Review Panel) review before merge."""
    # Check if ORP is in EXTRA_CHECKS
    signing_checks = context.get_signing_checks_for_pr()
    extra_checks = signing_checks.extra_checks

    if "orp" not in [c.lower() for c in extra_checks]:
        return False

    # Check if ORP has approved
    category_states = compute_category_approval_states(context)
    orp_state = category_states.get("orp", ApprovalState.PENDING)

    return orp_state != ApprovalState.APPROVED


def get_linked_prs(context: PRContext) -> List[str]:
    """Get list of linked PRs that were tested together with this PR."""
    linked = []

    # Check test parameters for 'with' PRs
    if context.test_params:
        with_prs = context.test_params.get("PULL_REQUESTS", "")
        if with_prs:
            for pr_ref in with_prs.split(","):
                pr_ref = pr_ref.strip()
                if pr_ref and pr_ref != str(context.issue.number):
                    linked.append(pr_ref)

    return linked


def post_fully_signed_messages(
    context: PRContext, old_labels: Set[str], new_labels: Set[str]
) -> None:
    """
    Post fully signed messages if PR/Issue transitions to fully signed state.

    Args:
        context: PR processing context
        old_labels: Labels before processing
        new_labels: Labels after processing
    """
    if context.is_pr:
        # Check for PR becoming fully signed
        if "fully-signed" in new_labels and "fully-signed" not in old_labels:
            message = get_fully_signed_message(context)
            post_bot_comment(context, message, "fully_signed")

        # Check for draft PR becoming fully signed
        if "fully-signed-draft" in new_labels and "fully-signed-draft" not in old_labels:
            user = context.pr.user.login if context.pr else "author"
            message = (
                f"{format_mention(context, user)} if this PR is ready to be reviewed by the "
                f'release team, please remove the "Draft" status.'
            )
            post_bot_comment(context, message, "fully_signed_draft")
    else:
        # Check for issue becoming fully signed
        category_states = compute_category_approval_states(context)
        all_approved = (
            all(state == ApprovalState.APPROVED for state in category_states.values())
            if category_states
            else False
        )

        if all_approved and category_states:
            # Check if we haven't already posted this
            post_bot_comment(
                context,
                "This issue is fully signed and ready to be closed.",
                "issue_fully_signed",
            )


# =============================================================================
# PROPERTIES FILE CREATION
# =============================================================================


def create_property_file(filename: str, parameters: Dict[str, Any], dry_run: bool) -> None:
    """
    Create a properties file with the given parameters.

    Args:
        filename: Output filename
        parameters: Dict of key=value pairs to write
        dry_run: If True, don't actually create the file
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would create properties file: {filename}")
        logger.debug(f"Properties: {parameters}")
        return

    logger.info(f"Creating properties file: {filename}")
    with open(filename, "w") as f:
        for key, value in parameters.items():
            f.write(f"{key}={value}\n")


def create_test_properties_file(
    context: PRContext,
    parameters: Dict[str, str],
    abort: bool = False,
    req_type: str = "tests",
) -> None:
    """
    Create a properties file to trigger tests.

    Args:
        context: PR processing context
        parameters: Test parameters
        abort: If True, create abort trigger
        req_type: Request type (tests, code-checks, etc.)
    """
    if abort:
        req_type = "abort"

    repository = f"{context.repo_org}/{context.repo_name}"

    # Determine if this should be a user-tests type
    if req_type == "tests":
        if context.repo_org not in EXTERNAL_REPOS:
            req_type = "user-tests"
        else:
            try:
                if not getattr(context.repo_config, "CMS_STANDARD_TESTS", True):
                    req_type = "user-tests"
            except Exception:
                pass

    # Build filename
    repo_slug = repository.replace("/", "-")
    pr_number = context.issue.number
    filename = f"trigger-{req_type}-{repo_slug}-{pr_number}.properties"

    # Add Jenkins slave label if configured
    try:
        slave_label = getattr(context.repo_config, "JENKINS_SLAVE_LABEL", None)
        if slave_label:
            parameters["RUN_LABEL"] = slave_label
    except Exception:
        pass

    create_property_file(filename, parameters, context.dry_run)


def build_test_parameters(context: PRContext, test_request: "TestRequest") -> Dict[str, str]:
    """
    Build parameters dict for a test request.

    Combines test_request values with context.test_params.

    Args:
        context: PR processing context
        test_request: The test request to build parameters for

    Returns:
        Dict of test parameters
    """
    params: Dict[str, str] = {}

    # Start with test_params from 'test parameters:' command
    params.update(context.test_params)

    # Add PR reference
    pr_ref = f"{context.repo_org}/{context.repo_name}#{context.issue.number}"
    prs = [pr_ref]
    if test_request.prs:
        prs.extend(test_request.prs)
    params["PULL_REQUESTS"] = " ".join(prs)

    # Context prefix
    params["CONTEXT_PREFIX"] = "cms"

    # Workflows
    if test_request.workflows:
        params["MATRIX_EXTRAS"] = test_request.workflows

    # Release/architecture
    if test_request.queue:
        if "/" in test_request.queue:
            release, arch = test_request.queue.split("/", 1)
            params["RELEASE_FORMAT"] = release
            params["ARCHITECTURE_FILTER"] = arch
        elif re.fullmatch(ARCH_PATTERN, test_request.queue):
            params["ARCHITECTURE_FILTER"] = test_request.queue
        else:
            params["RELEASE_FORMAT"] = test_request.queue

    # Build options
    if test_request.build_full:
        params["BUILD_FULL_CMSSW"] = "true"

    if test_request.extra_packages:
        params["EXTRA_CMSSW_PACKAGES"] = test_request.extra_packages

    # Build-only flag (build command vs test command)
    if test_request.verb == "build":
        params["BUILD_ONLY"] = "true"

    return params


def create_code_checks_properties(
    context: PRContext,
    tool_conf: Optional[str] = None,
    apply_patch: bool = False,
) -> None:
    """
    Create properties file for code-checks trigger.

    Args:
        context: PR processing context
        tool_conf: Optional tool configuration path
        apply_patch: Whether to apply the patch after checks
    """
    params = {
        "PULL_REQUEST": str(context.issue.number),
        "CONTEXT_PREFIX": "cms",
    }

    if tool_conf:
        params["CMSSW_TOOL_CONF"] = tool_conf

    params["APPLY_PATCH"] = str(apply_patch).lower()

    create_test_properties_file(context, params, req_type="code-checks")


def create_abort_properties(context: PRContext) -> None:
    """
    Create properties file to abort running tests.

    Args:
        context: PR processing context
    """
    params = {
        "PULL_REQUEST": str(context.issue.number),
    }
    create_test_properties_file(context, params, abort=True)


def create_cms_bot_test_properties(pr) -> None:
    """
    Create properties file for cms-bot self-test.

    Called when a PR is made to cms-sw/cms-bot by core/externals L2.

    Args:
        pr: The pull request object
    """
    params = {
        "CMS_BOT_TEST_BRANCH": pr.head.ref,
        "FORCE_PULL_REQUEST": str(pr.number),
        "CMS_BOT_TEST_PRS": f"cms-sw/cms-bot#{pr.number}",
    }

    with open("cms-bot.properties", "w") as f:
        for key, value in params.items():
            f.write(f"{key}={value}\n")

    logger.info(f"Created cms-bot.properties for PR #{pr.number}")


def create_new_data_repo_properties(issue_number: int, dry_run: bool) -> None:
    """
    Create properties file for new data repo issue.

    Args:
        issue_number: The issue number
        dry_run: If True, don't actually create the file
    """
    filename = f"query-new-data-repo-issues-{issue_number}.properties"
    params = {"ISSUE_NUMBER": str(issue_number)}
    create_property_file(filename, params, dry_run)


def check_commit_and_file_counts(context: PRContext, dryRun: bool) -> Optional[Dict[str, Any]]:
    """
    Check if PR has too many commits or files.

    This function:
    1. Scans comments to detect if bot has already warned
    2. Checks if +commit-count or +file-count override was given
    3. Posts warnings if needed
    4. Returns early result dict if PR should be blocked

    Args:
        context: PR processing context
        dryRun: If True, don't post comments

    Returns:
        Dict with block result if PR should be blocked, None otherwise
    """
    if not context.pr:
        return None

    commit_count = context.pr.commits
    file_count = context.pr.changed_files

    # Scan existing comments for bot warnings
    for comment in context.comments:
        body = comment.body or ""
        first_line = body.split("\n")[0] if body else ""

        # Check for commit count warnings
        if "This PR contains many commits" in first_line:
            if commit_count < TOO_MANY_COMMITS_FAIL_THRESHOLD:
                context.warned_too_many_commits = True
        elif "This PR contains too many commits" in first_line:
            context.warned_too_many_commits = True

        # Check for file count warnings
        if "This PR touches many files" in first_line:
            if file_count < TOO_MANY_FILES_FAIL_THRESHOLD:
                context.warned_too_many_files = True
        elif "This PR touches too many files" in first_line:
            context.warned_too_many_files = True

    # Format trackers for mention
    trackers_mention = ", ".join(format_mention(context, t) for t in CMSSW_ISSUES_TRACKERS)

    # Check commit count
    if commit_count >= TOO_MANY_COMMITS_WARN_THRESHOLD:
        if commit_count >= TOO_MANY_COMMITS_FAIL_THRESHOLD:
            # Hard block - no override possible
            if not context.warned_too_many_commits:
                msg = (
                    f"This PR contains too many commits ({commit_count} >= "
                    f"{TOO_MANY_COMMITS_FAIL_THRESHOLD}) and will not be processed.\n"
                    "Please ensure you have selected the correct target branch and "
                    "consider squashing unnecessary commits.\n"
                    "The processing of this PR will resume once the commit count "
                    "drops below the limit."
                )
                post_bot_comment(context, msg, "too_many_commits_fail")
                logger.warning(f"PR blocked: too many commits ({commit_count})")

            # Always block at FAIL threshold - cannot be overridden
            context.blocked_by_commit_count = True
            flush_pending_comments(context)  # Flush before early return
            return {
                "pr_number": context.issue.number,
                "is_pr": True,
                "blocked": True,
                "reason": f"Too many commits ({commit_count})",
                "pr_state": None,
                "categories": {},
                "holds": [],
                "labels": [],
                "messages": [],
                "tests_triggered": [],
            }
        else:
            # Warning level - can be overridden
            if not context.warned_too_many_commits and not context.ignore_commit_count:
                msg = (
                    f"This PR contains many commits ({commit_count} >= "
                    f"{TOO_MANY_COMMITS_WARN_THRESHOLD}) and will not be processed. "
                    "Please ensure you have selected the correct target branch and "
                    "consider squashing unnecessary commits.\n"
                    f"{trackers_mention}, to re-enable processing of this PR, "
                    "you can write `+commit-count` in a comment. Thanks."
                )
                post_bot_comment(context, msg, "too_many_commits_warn")
                logger.warning(f"PR warned: many commits ({commit_count})")

            # Block if not overridden
            if not context.ignore_commit_count:
                context.blocked_by_commit_count = True
                flush_pending_comments(context)  # Flush before early return
                return {
                    "pr_number": context.issue.number,
                    "is_pr": True,
                    "blocked": True,
                    "reason": f"Too many commits ({commit_count})",
                    "pr_state": None,
                    "categories": {},
                    "holds": [],
                    "labels": [],
                    "messages": [],
                    "tests_triggered": [],
                }

    # Check file count (CMSSW repo only)
    if context.cmssw_repo and file_count >= TOO_MANY_FILES_WARN_THRESHOLD:
        if file_count >= TOO_MANY_FILES_FAIL_THRESHOLD:
            # Hard block - no override possible
            if not context.warned_too_many_files:
                msg = (
                    f"This PR touches too many files ({file_count} >= "
                    f"{TOO_MANY_FILES_FAIL_THRESHOLD}) and will not be processed.\n"
                    "Please ensure you have selected the correct target branch and "
                    "consider splitting this PR into several.\n"
                    "The processing of this PR will resume once the number of "
                    "changed files drops below the limit."
                )
                post_bot_comment(context, msg, "too_many_files_fail")
                logger.warning(f"PR blocked: too many files ({file_count})")

            # Always block at FAIL threshold - cannot be overridden
            context.blocked_by_file_count = True
            flush_pending_comments(context)  # Flush before early return
            return {
                "pr_number": context.issue.number,
                "is_pr": True,
                "blocked": True,
                "reason": f"Too many files ({file_count})",
                "pr_state": None,
                "categories": {},
                "holds": [],
                "labels": [],
                "messages": [],
                "tests_triggered": [],
            }
        else:
            # Warning level - can be overridden
            if not context.warned_too_many_files and not context.ignore_file_count:
                msg = (
                    f"This PR touches many files ({file_count} >= "
                    f"{TOO_MANY_FILES_WARN_THRESHOLD}) and will not be processed. "
                    "Please ensure you have selected the correct target branch and "
                    "consider splitting this PR into several.\n"
                    f"{trackers_mention}, to re-enable processing of this PR, "
                    "you can write `+file-count` in a comment. Thanks."
                )
                post_bot_comment(context, msg, "too_many_files_warn")
                logger.warning(f"PR warned: many files ({file_count})")

            # Block if not overridden
            if not context.ignore_file_count:
                context.blocked_by_file_count = True
                flush_pending_comments(context)  # Flush before early return
                return {
                    "pr_number": context.issue.number,
                    "is_pr": True,
                    "blocked": True,
                    "reason": f"Too many files ({file_count})",
                    "pr_state": None,
                    "categories": {},
                    "holds": [],
                    "labels": [],
                    "messages": [],
                    "tests_triggered": [],
                }

    return None


def post_welcome_message(context: PRContext) -> None:
    """
    Post welcome message for new PRs/Issues.

    For draft PRs, the welcome message is delayed until the PR exits draft state.

    For CMSSW repo PRs, includes:
    - Package list with categories
    - New package warning if applicable
    - Patch branch warning if applicable
    - Release managers notification

    Args:
        context: PR processing context
    """
    # Skip welcome message for draft PRs - will post when it exits draft
    if context.is_draft:
        logger.debug("Skipping welcome message for draft PR")
        return

    entity_type = "Pull Request" if context.is_pr else "Issue"
    msg_prefix = NEW_PR_PREFIX if context.is_pr else NEW_ISSUE_PREFIX

    # Check if welcome message was already posted
    for comment in context.comments:
        if context.cmsbuild_user and comment.user.login == context.cmsbuild_user:
            body = comment.body or ""
            # Check for either prefix style
            if msg_prefix in body or f"A new {entity_type} was created by" in body:
                context.welcome_message_posted = True
                return

    # Get author
    author = context.issue.user.login if context.issue else "unknown"
    timestamp = datetime.now(tz=timezone.utc)

    # Get L2s for all signing categories
    all_l2s = set()
    for cat in context.signing_categories:
        cat_l2s = get_category_l2s(context.repo_config, cat, timestamp)
        all_l2s.update(cat_l2s)

    # Build L2 mention list
    l2_mentions = ", ".join(format_mention(context, l2) for l2 in sorted(all_l2s))

    # Build watchers message
    watchers_msg = ""
    if context.watchers:
        watcher_mentions = ", ".join(format_mention(context, w) for w in sorted(context.watchers))
        watchers_msg = f"{watcher_mentions} this is something you requested to watch as well.\n"

    # Build backport message (uses BACKPORT_STR from cms_static)
    backport_msg = ""
    if context.backport_of:
        backport_msg = f"{BACKPORT_STR}{context.backport_of}\n"

    # CMSSW repo has more detailed welcome message for PRs
    if context.cmssw_repo and context.is_pr and context.pr:
        msg = _build_cmssw_welcome_message(
            context, author, l2_mentions, watchers_msg, backport_msg, timestamp
        )
    else:
        # Simple message for non-CMSSW repos or issues
        commands_url = "http://cms-sw.github.io/cms-bot-cmssw-issues.html"
        msg = (
            f"{msg_prefix} {format_mention(context, author)}.\n\n"
            f"{l2_mentions} can you please review it and eventually sign/assign? Thanks.\n"
            f"{watchers_msg}"
            f"{backport_msg}"
            f'cms-bot commands are listed <a href="{commands_url}">here</a>\n'
        )

    post_bot_comment(context, msg, "welcome")
    context.welcome_message_posted = True


def _build_cmssw_welcome_message(
    context: PRContext,
    author: str,
    l2_mentions: str,
    watchers_msg: str,
    backport_msg: str,
    timestamp: datetime,
) -> str:
    """
    Build the detailed welcome message for CMSSW repo PRs.

    Includes package list, new package warnings, patch branch warnings,
    and release manager notifications.
    """
    pr = context.pr
    branch = pr.base.ref

    # Build package list with categories
    pkg_lines = []
    new_packages = []
    all_known_packages = set(CMSSW_CATEGORIES.keys()) if CMSSW_CATEGORIES else set()

    for pkg in sorted(context.packages):
        pkg_cats = get_package_categories(pkg)
        if pkg_cats:
            pkg_lines.append(f"- {pkg} (**{', '.join(sorted(pkg_cats))}**)")
        else:
            pkg_lines.append(f"- {pkg} (**new**)")
            if pkg not in all_known_packages:
                new_packages.append(pkg)

    packages_str = "\n".join(pkg_lines) if pkg_lines else "- (none)"

    # Build new package message
    new_package_msg = ""
    if new_packages:
        new_package_msg = (
            "\nThe following packages do not have a category, yet:\n\n"
            + "\n".join(new_packages)
            + "\n"
            + "Please create a PR for https://github.com/cms-sw/cms-bot/blob/master/categories_map.py "
            "to assign category\n"
        )
        context.signing_categories.add("new-package")

    # Build patch branch warning
    patch_warning = ""
    if "patchX" in branch:
        base_release = branch.replace("_patchX", "")
        base_branch = re.sub(r"[0-9]+$", "X", base_release)
        patch_warning = (
            f"Note that this branch is designed for requested bug fixes "
            f"specific to the {base_release} release.\n"
            f"If you wish to make a pull request for the {base_branch} "
            f"release cycle, please use the {base_branch} branch instead\n"
        )

    # Build release managers message
    release_managers_msg = ""
    extra_rm = get_release_managers(branch)

    # For CMSDIST, also get managers for the base branch
    if context.repo_name == GH_CMSDIST_REPO:
        parts = branch.split("/")
        if len(parts) >= 2:
            br = "_".join(parts[-1].split("_")[:3]) + "_X"
            if br:
                extra_rm = extra_rm + get_release_managers(br)

    release_managers = list(set(extra_rm + list(CMSSW_ORP)))
    if release_managers:
        rm_mentions = ", ".join(format_mention(context, rm) for rm in sorted(release_managers))
        release_managers_msg = f"{rm_mentions} you are the release manager for this.\n"

    # Build the full message
    commands_url = "http://cms-sw.github.io/cms-bot-cmssw-cmds.html"
    msg = (
        f"{NEW_PR_PREFIX} {format_mention(context, author)} for {branch}.\n\n"
        f"It involves the following packages:\n\n"
        f"{packages_str}\n\n"
        f"{new_package_msg}"
        f"{l2_mentions} can you please review it and eventually sign? Thanks.\n"
        f"{watchers_msg}"
        f"{release_managers_msg}"
        f"{patch_warning}"
        f"{backport_msg}"
        f'cms-bot commands are listed <a href="{commands_url}">here</a>\n'
    )

    return msg


def post_pr_updated_message(context: PRContext, new_commit_sha: str) -> None:
    """
    Post message when PR is updated with a new commit.

    Args:
        context: PR processing context
        new_commit_sha: SHA of the new commit
    """
    if not context.is_pr or not context.pr:
        return

    pr_number = context.issue.number

    # For draft PRs, just notify without resign request
    if context.is_draft:
        msg = f"Pull request #{pr_number} was updated."
        post_bot_comment(context, msg, "pr_updated", hash(new_commit_sha))
        return

    # Get L2s for categories that need signatures (not yet approved)
    timestamp = datetime.now(tz=timezone.utc)
    category_states = compute_category_approval_states(context)

    pending_l2s = set()
    for cat, state in category_states.items():
        if state != ApprovalState.APPROVED:
            cat_l2s = get_category_l2s(context.repo_config, cat, timestamp)
            pending_l2s.update(cat_l2s)

    # Build resign message
    resign_msg = ""
    if pending_l2s:
        signers = ", ".join(format_mention(context, l2) for l2 in sorted(pending_l2s))
        resign_msg = f" {signers} can you please check and sign again."

    # Build watchers message
    watchers_msg = ""
    if context.watchers:
        watcher_mentions = ", ".join(format_mention(context, w) for w in sorted(context.watchers))
        watchers_msg = f"\n\n{watcher_mentions} this is something you requested to watch as well."

    # Build new categories message (similar to welcome message format)
    new_categories_msg = ""
    new_categories = getattr(context, "_new_categories", set())
    if new_categories:
        # Get packages for new categories
        new_pkg_lines = []
        for fv_key in context.cache.current_file_versions:
            if fv_key in context.cache.file_versions:
                fv = context.cache.file_versions[fv_key]
                pkg = file_to_package(context.repo_config, fv.filename)
                if pkg:
                    # Check if this package has any of the new categories
                    pkg_new_cats = [c for c in fv.categories if c in new_categories]
                    if pkg_new_cats:
                        new_pkg_lines.append(f"- {pkg} (**{', '.join(sorted(pkg_new_cats))}**)")

        if new_pkg_lines:
            # Remove duplicates and sort
            unique_pkg_lines = sorted(set(new_pkg_lines))
            new_categories_msg = "\n\nThe following packages are now also affected:\n" + "\n".join(
                unique_pkg_lines
            )

            # Add L2 mentions for new categories
            new_cat_l2s = set()
            for cat in new_categories:
                cat_l2s = get_category_l2s(context.repo_config, cat, timestamp)
                new_cat_l2s.update(cat_l2s)

            if new_cat_l2s:
                new_l2_mentions = ", ".join(
                    format_mention(context, l2) for l2 in sorted(new_cat_l2s)
                )
                new_categories_msg += f"\n\n{new_l2_mentions} can you please review and sign?"

    msg = f"Pull request #{pr_number} was updated.{resign_msg}{new_categories_msg}{watchers_msg}"
    post_bot_comment(context, msg, "pr_updated", hash(new_commit_sha))


def check_for_new_commits(context: PRContext) -> None:
    """
    Check if there are new commits since the last bot message.

    Posts a "PR updated" message if new commits are detected.

    Args:
        context: PR processing context
    """
    if not context.is_pr or not context.commits:
        return

    # Get the SHA of the latest commit
    latest_commit = context.commits[-1]
    latest_sha = latest_commit.sha if hasattr(latest_commit, "sha") else str(latest_commit)

    # Check if we've already posted an update for this commit
    # Look for existing "PR was updated" messages in comments
    for comment in context.comments:
        if context.cmsbuild_user and comment.user.login == context.cmsbuild_user:
            body = comment.body or ""
            # Check if this comment is for this specific commit
            if f"<!--pr_updated:{hash(latest_sha)}-->" in body:
                logger.debug(f"Already posted update for commit {latest_sha[:8]}")
                return

    # Check if we've already posted the welcome message
    # If not, this is the first time seeing the PR - don't post update
    if not context.welcome_message_posted:
        # Check if welcome message exists
        entity_type = "Pull Request" if context.is_pr else "Issue"
        for comment in context.comments:
            if context.cmsbuild_user and comment.user.login == context.cmsbuild_user:
                body = comment.body or ""
                if f"A new {entity_type} was created by" in body:
                    context.welcome_message_posted = True
                    break

        if not context.welcome_message_posted:
            # This is a new PR, don't post "updated" message
            logger.debug("New PR/Issue, skipping update message")
            return

    # Check if there are commits newer than the last bot comment
    last_bot_comment_time: Optional[datetime] = None
    for comment in context.comments:
        if context.cmsbuild_user and comment.user.login == context.cmsbuild_user:
            comment_time = get_comment_timestamp(comment)
            if last_bot_comment_time is None or comment_time > last_bot_comment_time:
                last_bot_comment_time = comment_time

    if last_bot_comment_time:
        # Check if the latest commit is after the last bot comment
        try:
            commit_time = ensure_tz_aware(latest_commit.commit.author.date)
            if commit_time > last_bot_comment_time:
                logger.info(f"New commit detected: {latest_sha[:8]}")
                post_pr_updated_message(context, latest_sha)
        except Exception as e:
            logger.warning(f"Could not compare commit times: {e}")


# =============================================================================
# MAIN PROCESSING FUNCTION
# =============================================================================


def process_pr(
    repo_config: types.ModuleType,
    gh,
    repo,
    issue,
    dryRun: bool,
    cmsbuild_user: Optional[str] = None,
    force: bool = False,
    loglevel: Union[str, int] = "INFO",
) -> Dict[str, Any]:
    """
    Main entry point for processing a PR or Issue.

    Args:
        repo_config: Repository configuration module
        gh: PyGithub GitHub instance
        repo: PyGithub Repository object
        issue: PyGithub Issue or PullRequest object
        dryRun: If True, don't make any changes
        cmsbuild_user: Bot's username (to skip own comments)
        force: If True, process PR/Issue even if marked with <cms-bot></cms-bot>
        loglevel: Logging level (string or int)

    Returns:
        Dict with processing results
    """
    setup_logging(loglevel)

    # Initialize label patterns for auto-labeling
    initialize_labels(repo_config)

    # Determine if this is a PR or Issue
    is_pr = hasattr(issue, "pull_request") and issue.pull_request is not None
    # Alternative check for PyGithub PullRequest objects
    if not is_pr:
        is_pr = hasattr(issue, "merged")

    if is_pr:
        logger.info(f"Processing PR #{issue.number} in {repo.full_name}")
    else:
        logger.info(f"Processing Issue #{issue.number} in {repo.full_name}")

    # Get PR object if this is a PR
    pr = None
    if is_pr:
        try:
            pr = issue.as_pull_request()
        except AttributeError:
            # Already a PullRequest object
            pr = issue
        except Exception:
            pr = repo.get_pull(issue.number)

    # Get body for ignore/notify checks
    body = (pr.body if pr else issue.body) or ""

    # Check if should be ignored (unless force flag is set)
    if not force and should_ignore_issue(repo_config, repo, issue):
        entity_type = "PR" if is_pr else "Issue"
        logger.info(f"{entity_type} #{issue.number} should be ignored, skipping processing")
        return {
            "pr_number": issue.number,
            "skipped": True,
            "reason": "ignored",
            "is_pr": is_pr,
            "pr_state": None,
            "categories": {},
            "holds": [],
            "messages": [],
            "tests_triggered": [],
        }

    # Check if notifications should omit @ symbol
    notify_without_at = should_notify_without_at(body)
    if notify_without_at:
        logger.debug("Has <notify></notify> tag, will omit @ in mentions")

    # Fetch all comments once and use throughout processing
    comments = list(issue.get_comments())
    logger.debug(f"Fetched {len(comments)} comments")

    # Fetch commits once for PRs
    commits = []
    if is_pr and pr:
        try:
            commits = list(pr.get_commits())
            logger.debug(f"Fetched {len(commits)} commits")
        except Exception as e:
            logger.warning(f"Failed to fetch commits: {e}")

    # Load cache from comments
    cache = load_cache_from_comments(comments)

    # Use global command registry
    command_registry = get_global_registry()

    # Create context with comments and commits
    context = PRContext(
        repo_config=repo_config,
        gh=gh,
        repo=repo,
        issue=issue,
        pr=pr,
        cache=cache,
        command_registry=command_registry,
        dry_run=dryRun,
        cmsbuild_user=cmsbuild_user,
        is_pr=is_pr,
        comments=comments,
        commits=commits,
        notify_without_at=notify_without_at,
    )

    # Set repository info (these are stored, computed properties derive from them)
    context.repo_name = repo.name
    context.repo_org = repo.owner.login if hasattr(repo.owner, "login") else repo.owner

    # Log draft state (property computes it automatically)
    if context.is_draft:
        logger.debug("PR is in draft state, disabling @-mentions")

    # Handle cms-bot self-test (PRs to cms-sw/cms-bot by core/externals L2s)
    if (
        is_pr
        and pr
        and repo.full_name == "cms-sw/cms-bot"
        and os_getenv("CMS_BOT_TEST_BRANCH", "master") == "master"
        and pr.state != "closed"
    ):
        author = issue.user.login
        author_categories = get_user_l2_categories(
            repo_config, author, datetime.now(tz=timezone.utc)
        )
        if "externals" in author_categories or "core" in author_categories:
            create_cms_bot_test_properties(pr)
            return {
                "pr_number": issue.number,
                "is_pr": is_pr,
                "cms_bot_test": True,
                "reason": "cms-bot self-test triggered",
                "pr_state": None,
                "categories": {},
                "holds": [],
                "labels": [],
                "messages": [],
                "tests_triggered": [],
            }

    # PR-specific startup processing
    if is_pr and pr:
        # Check for PRs to development branch that should go to master
        if context.cmssw_repo and context.cms_repo and pr.base.ref == CMSSW_DEVEL_BRANCH:
            if pr.state != "closed":
                logger.error("This pull request must go in to master branch")
                if not dryRun:
                    pr.edit(base="master")
                    msg = (
                        f"{format_mention(context, pr.user.login)}, {CMSSW_DEVEL_BRANCH} branch is closed "
                        "for direct updates. cms-bot is going to move this PR to master branch.\n"
                        "In future, please use cmssw master branch to submit your changes.\n"
                    )
                    issue.create_comment(msg)
                return {
                    "pr_number": issue.number,
                    "is_pr": is_pr,
                    "redirected": True,
                    "reason": f"Redirected from {CMSSW_DEVEL_BRANCH} to master",
                    "pr_state": None,
                    "categories": {},
                    "holds": [],
                    "messages": [],
                    "tests_triggered": [],
                }

        # Check if PR is to a closed branch
        if is_closed_branch(pr.base.ref):
            context.must_close = True

        # Process changes for the PR to determine required signatures
        chg_files: List[str] = []

        # Get signing checks based on repo and branch
        signing_checks = context.get_signing_checks_for_pr()

        # Add pre_checks categories (like code-checks) to signing_categories
        for cat in signing_checks.pre_checks:
            context.signing_categories.add(cat)

        if context.cmssw_repo or not context.external_repo:
            if context.cmssw_repo:
                update_milestone(repo, issue, pr, dryRun)

            # Fetch PR files once and cache both formats
            files_with_sha, chg_files = get_pr_files_info(pr)
            context._pr_files_with_sha = files_with_sha
            context._changed_files = chg_files
            context.packages = set(file_to_package(repo_config, f) for f in chg_files)
            add_nonblocking_labels(chg_files, context.pending_labels)
            context.create_test_property = True
        else:
            # External repo handling
            # Add 'externals' category if it's in extra_checks
            if "externals" in signing_checks.extra_checks:
                context.signing_categories.add("externals")
            context.packages = {f"externals/{repo.full_name}"}
            ex_pkg = external_to_package(repo.full_name)
            if ex_pkg:
                context.packages.add(ex_pkg)

            if (context.repo_org != GH_CMSSW_ORGANIZATION) or (
                context.repo_name in VALID_CMS_SW_REPOS_FOR_TESTS
            ):
                context.create_test_property = True

            # Skip invalid CMSDIST branches
            if context.repo_name == GH_CMSDIST_REPO:
                if not re.match(VALID_CMSDIST_BRANCHES, pr.base.ref):
                    logger.error("Skipping PR as it does not belong to valid CMSDIST branch")
                    return {
                        "pr_number": issue.number,
                        "is_pr": is_pr,
                        "skipped": True,
                        "reason": "Invalid CMSDIST branch",
                        "pr_state": None,
                        "categories": {},
                        "holds": [],
                        "messages": [],
                        "tests_triggered": [],
                    }

            # Check for non-blocking labels in external repos
            try:
                if getattr(repo_config, "NONBLOCKING_LABELS", False):
                    files_with_sha, chg_files = get_pr_files_info(pr)
                    context._pr_files_with_sha = files_with_sha
                    context._changed_files = chg_files
                    add_nonblocking_labels(chg_files, context.pending_labels)
            except Exception:
                pass

        # Build package categories and update signing categories (common to all repos)
        if context.packages:
            logger.info(f"Following packages affected: {', '.join(sorted(context.packages))}")
            pkg_categories: Set[str] = set()
            for package in context.packages:
                pkg_cats = get_package_categories(package)
                pkg_categories.update(pkg_cats)
            context.signing_categories.update(pkg_categories)

        # Set create_test_property to False if PR is closed
        if pr.state == "closed":
            context.create_test_property = False

        # Load watchers based on changed files and categories
        if chg_files:
            context.watchers = get_watchers(context, chg_files, datetime.now(tz=timezone.utc))

        # Update file states (sets current_file_versions)
        changed_files, new_categories = update_file_states(context)
        if changed_files:
            logger.info(f"Changed files: {changed_files}")
        if new_categories:
            logger.info(f"New categories: {new_categories}")

        # Store new categories for use in PR updated message
        context._new_categories = new_categories

        # Check for new commits and post update message if needed
        check_for_new_commits(context)

    # Process all comments
    process_all_comments(context)

    # Process deferred build/test commands (after all comments seen)
    if is_pr:
        process_pending_build_test_commands(context)

    # Check commit and file counts (for PRs only)
    if is_pr and pr:
        block_result = check_commit_and_file_counts(context, dryRun)
        if block_result:
            # Save cache before returning
            save_cache_to_comments(issue, context.comments, cache, dryRun)
            return block_result

    # Update status (labels, etc.) for both PRs and Issues
    old_labels, new_labels = update_pr_status(context)

    # Post fully signed messages if state changed
    post_fully_signed_messages(context, old_labels, new_labels)

    # Post welcome message if this is the first time seeing this PR/Issue
    post_welcome_message(context)

    # PR-specific state determination and actions
    pr_state = None
    if is_pr:
        # Determine PR state
        pr_state = determine_pr_state(context)
        logger.info(f"PR state: {pr_state.value}")

        # Handle must_close (e.g., PR to closed branch)
        if context.must_close:
            if dryRun:
                logger.info("[DRY RUN] Would close issue (closed branch)")
            else:
                try:
                    issue.edit(state="closed")
                    logger.info("Issue closed (target branch is closed)")
                except Exception as e:
                    logger.error(f"Failed to close issue: {e}")
                    context.messages.append(f"Failed to close issue: {e}")

        # Handle automerge
        if getattr(repo_config, "AUTOMERGE", False) and can_merge(context):
            context.should_merge = True
            logger.info("PR eligible for automerge")

        # Perform merge if requested
        if context.should_merge:
            if dryRun:
                logger.info("[DRY RUN] Would merge PR")
            else:
                try:
                    pr.merge()
                    logger.info("PR merged successfully")
                except Exception as e:
                    logger.error(f"Failed to merge PR: {e}")
                    context.messages.append(f"Merge failed: {e}")

        # Handle abort tests
        if context.abort_tests and context.create_test_property:
            logger.info("Creating abort test properties file")
            create_abort_properties(context)

        # Trigger tests if requested
        if context.create_test_property:
            for test_request in context.tests_to_run:
                params = build_test_parameters(context, test_request)
                logger.info(
                    f"Creating test properties: {test_request.verb} triggered by {test_request.triggered_by}"
                )
                create_test_properties_file(context, params)

        # Handle code checks request
        if context.code_checks_requested:
            logger.info("Creating code-checks properties file")
            create_code_checks_properties(
                context,
                tool_conf=context.code_checks_tool_conf,
                apply_patch=context.code_checks_apply_patch,
            )

        # Check and process CI test results
        process_ci_test_results(context)
    else:
        # Issue-specific processing
        # Check for new data repo request issues
        if context.cmssw_repo and re.match(CREATE_REPO, issue.title or ""):
            logger.info(f"Creating new data repo properties for issue #{issue.number}")
            create_new_data_repo_properties(issue.number, dryRun)

    # Flush all pending bot comments
    flush_pending_comments(context)

    # Save cache
    save_cache_to_comments(issue, context.comments, cache, dryRun)

    # Generate status message (for both PRs and Issues)
    status_message = generate_status_message(context)

    # Compute category states for return value (for PRs)
    category_states = compute_category_approval_states(context) if is_pr else {}

    # Get check types for result
    signing_checks = context.get_signing_checks_for_pr() if is_pr else SigningChecks()
    pre_checks = signing_checks.pre_checks
    extra_checks = signing_checks.extra_checks

    # Collect all labels
    all_labels = set(context.pending_labels)

    # Return results
    return {
        "pr_number": issue.number,
        "is_pr": is_pr,
        "pr_state": pr_state.value if pr_state else None,
        "can_merge": can_merge(context) if is_pr else False,
        "categories": {
            name: {
                "state": state.value,
                "check_type": (
                    "pre_check"
                    if name in pre_checks
                    else "extra_check" if name in extra_checks else "regular"
                ),
            }
            for name, state in category_states.items()
        },
        "holds": [{"category": h.category, "user": h.user} for h in context.holds],
        "labels": sorted(all_labels),
        "messages": context.messages,
        "status_message": status_message,
        "tests_triggered": [
            {
                "verb": t.verb,
                "workflows": t.workflows,
                "prs": t.prs,
                "queue": t.queue,
                "build_full": t.build_full,
                "extra_packages": t.extra_packages,
                "triggered_by": t.triggered_by,
            }
            for t in context.tests_to_run
        ],
        "merged": context.should_merge and not dryRun,
    }


# =============================================================================
# UTILITY FUNCTIONS FOR EXTERNAL USE
# =============================================================================


def add_custom_command(
    name: str,
    pattern: str,
    handler: Callable[..., bool],
    acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
    description: str = "",
) -> None:
    """
    Add a custom command to the global registry.

    This allows external code to extend the bot with new commands.

    Args:
        name: Command identifier
        pattern: Regex pattern to match
        handler: Function(context, match, user, comment_id, timestamp) -> bool
        acl: Access control (list of users/categories or callback)
        description: Human-readable description
    """
    _global_registry.register(name, pattern, handler, acl, description)


def set_category_status(
    context: PRContext,
    category: str,
    status: ApprovalState,
    dry_run: bool = False,
) -> None:
    """
    Set the status of a category (e.g., tests, code-checks).

    This is typically called by external processes (CI, linters) to report results.
    It creates a synthetic file version for the category if needed, which allows
    the normal approval flow to work.

    Args:
        context: PR processing context
        category: Category name (e.g., "tests", "code-checks")
        status: Approval state to set
        dry_run: If True, only log the action
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would set {category} status to: {status.value}")
        return

    # Check if category already has a file version
    has_category = any(category in fv.categories for fv in context.cache.file_versions.values())

    if not has_category:
        # Add a synthetic file version for this category
        fv_key = f"::{category}::status"
        context.cache.file_versions[fv_key] = FileVersion(
            filename=f"::{category}",
            blob_sha="status",
            timestamp=datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            categories=[category],
        )

    logger.info(f"Set {category} status to: {status.value}")


if __name__ == "__main__":
    # This is just for testing/demonstration
    print("cms-bot module loaded successfully")
    print("Use process_pr() to process a PR")
    print("\nRegistered commands:")
    for cmd in _global_registry.commands:
        pr_flag = " (PR only)" if cmd.pr_only else ""
        print(f"  - {cmd.name}: {cmd.description}{pr_flag}")
