#!/usr/bin/env python3
"""
cms-bot: A GitHub bot for automating CI tests and PR reviews.

This bot is stateless except for a small cache stored in PR issue comments.
It handles code ownership, approval workflows, and merge automation.
"""

import base64
import gzip
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
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import forward_ports_map

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
CACHE_COMMENT_MARKER = "cms-bot internal usage<!--"
CACHE_COMMENT_END = "-->"

# Maximum size for a single comment (GitHub limit is ~65536, we use less for safety)
MAX_COMMENT_SIZE = 60000

# Reaction types
REACTION_PLUS_ONE = "+1"
REACTION_MINUS_ONE = "-1"

# Commit and file count thresholds
TOO_MANY_COMMITS_WARN_THRESHOLD = 150  # Warning level
TOO_MANY_COMMITS_FAIL_THRESHOLD = 240  # Hard block level (no override possible)
TOO_MANY_FILES_WARN_THRESHOLD = 1500  # Warning level
TOO_MANY_FILES_FAIL_THRESHOLD = 3001  # Hard block level (no override possible)

# Commands that can be processed from bot's own comments
# (for CI results, code-checks, etc.)
BOT_ALLOWED_COMMAND_PATTERNS = [
    r"^[+-]code-checks$",
    r"^[+-]1$",
    r"^[+-]\w+$",  # Category-specific approvals/rejections
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

# Regex patterns for PR description flags
RE_CMS_BOT_IGNORE = re.compile(r"<cms-bot>\s*</cms-bot>", re.IGNORECASE)
RE_NOTIFY_NO_AT = re.compile(r"<notify>\s*</notify>", re.IGNORECASE)

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
    snapshot = context.cache.get_current_snapshot()

    if not snapshot:
        return labels

    for fv_key in snapshot.changes:
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
class Snapshot:
    """
    Represents the state of all files at a point in time.

    Attributes:
        snapshot_id: Unique identifier for this snapshot
        timestamp: When the snapshot was taken
        changes: List of file version keys (filename::blob_sha)
    """

    snapshot_id: str
    timestamp: str
    changes: List[str] = field(default_factory=list)


@dataclass
class CommentInfo:
    """
    Cached information about a processed comment.

    Attributes:
        timestamp: When the comment was created (ISO format)
        first_line: First non-blank line of comment (for command detection)
        ctype: Command type detected (e.g., '+1', '-1', 'hold', 'test')
        categories: Categories affected by this command
        snapshot: Snapshot ID at time of comment (for signatures)
        user: Username who made the comment
        locked: If True, signature cannot be changed (commit happened after)
    """

    timestamp: str
    first_line: str
    ctype: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    snapshot: Optional[str] = None
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
        "snapshots": { "<id>": { "ts": ..., "changes": [...] } },  # PR state snapshots
        "comments": { "<comment_id>": { "ts": ..., "first_line": ..., ... } }  # Processed comments
    }
    """

    # Bot's reactions on comments (comment_id -> reaction)
    emoji: Dict[str, str] = field(default_factory=dict)

    # File versions (filename::sha -> FileVersion info)
    file_versions: Dict[str, FileVersion] = field(default_factory=dict)

    # Snapshots of PR state (snapshot_id -> Snapshot)
    snapshots: Dict[str, Snapshot] = field(default_factory=dict)

    # Processed comments (comment_id -> CommentInfo)
    comments: Dict[str, CommentInfo] = field(default_factory=dict)

    # Runtime state (not persisted)
    current_snapshot_id: str = ""

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
            "snapshots": {
                sid: {
                    "ts": snap.timestamp,
                    "changes": snap.changes,
                }
                for sid, snap in self.snapshots.items()
            },
            "comments": {
                cid: {
                    "ts": ci.timestamp,
                    "first_line": ci.first_line,
                    **({"ctype": ci.ctype} if ci.ctype else {}),
                    **({"cats": ci.categories} if ci.categories else {}),
                    **({"snapshot": ci.snapshot} if ci.snapshot else {}),
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

        # Load snapshots
        for sid, snap_data in data.get("snapshots", {}).items():
            cache.snapshots[sid] = Snapshot(
                snapshot_id=sid,
                timestamp=snap_data.get("ts", ""),
                changes=snap_data.get("changes", []),
            )

        # Load comments
        for cid, ci_data in data.get("comments", {}).items():
            cache.comments[str(cid)] = CommentInfo(
                timestamp=ci_data.get("ts", ""),
                first_line=ci_data.get("first_line", ""),
                ctype=ci_data.get("ctype"),
                categories=ci_data.get("cats", []),
                snapshot=ci_data.get("snapshot"),
                user=ci_data.get("user"),
                locked=ci_data.get("locked", False),
            )

        return cache

    def get_current_snapshot(self) -> Optional[Snapshot]:
        """Get the current (latest) snapshot."""
        if self.current_snapshot_id and self.current_snapshot_id in self.snapshots:
            return self.snapshots[self.current_snapshot_id]
        return None

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
    """Compress cache data using gzip + base64."""
    compressed = gzip.compress(data.encode("utf-8"))
    return base64.b64encode(compressed).decode("utf-8")


def decompress_cache(data: str) -> str:
    """Decompress cache data from gzip + base64."""
    compressed = base64.b64decode(data.encode("utf-8"))
    return gzip.decompress(compressed).decode("utf-8")


def load_cache_from_comments(comments: List[Any]) -> BotCache:
    """
    Load bot cache from PR issue comments.

    The cache is stored in comments with format:
    'cms-bot internal usage<!-- {JSON or compressed data} -->'

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

    Creates or updates cache comments. Will compress and split if needed.

    Args:
        issue: The issue/PR object (used for creating new comments)
        comments: List of existing comment objects
        cache: The cache to save
        dry_run: If True, don't actually save
    """
    data = json.dumps(cache.to_dict(), separators=(",", ":"))

    # Check if compression is needed
    if len(data) > MAX_COMMENT_SIZE:
        data = compress_cache(data)

    # Split into chunks if still too large
    chunks = [data[i : i + MAX_COMMENT_SIZE] for i in range(0, len(data), MAX_COMMENT_SIZE)]

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
            # Update existing comment
            existing_cache_comments[i].edit(comment_body)
            logger.debug(f"Updated cache comment {i + 1}/{len(chunks)}")
        else:
            # Create new comment
            issue.create_comment(comment_body)
            logger.debug(f"Created cache comment {i + 1}/{len(chunks)}")

    # Delete extra old comments
    for comment in existing_cache_comments[len(chunks) :]:
        comment.delete()
        logger.debug("Deleted extra cache comment")


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


def get_checks_for_pr(repo_config: types.ModuleType, pr_number: int, check_type: str) -> List[str]:
    """
    Get the list of required checks for a PR based on its number.

    The checks are defined as List[Tuple[int, List[str]]] where:
    - First item is the minimum PR number for which the checks apply
    - Second item is the list of required signature categories

    The function finds the highest applicable PR threshold and returns
    its associated checks.

    Args:
        repo_config: Repository configuration module
        pr_number: PR number
        check_type: Either "PRE_CHECKS" or "EXTRA_CHECKS"

    Returns:
        List of category names that need signatures
    """
    checks_list = getattr(repo_config, check_type, [])

    if not checks_list:
        return []

    # Find the highest threshold that applies to this PR
    applicable_checks = []
    for min_pr, checks in checks_list:
        if pr_number >= min_pr:
            applicable_checks = checks

    return applicable_checks


def get_pre_checks(repo_config: types.ModuleType, pr_number: int) -> List[str]:
    """
    Get PRE_CHECKS categories for a PR.

    PRE_CHECKS are signatures that:
    - Reset on every new commit
    - Are required before running tests (build/test commands)

    Args:
        repo_config: Repository configuration module
        pr_number: PR number

    Returns:
        List of category names required before tests
    """
    return get_checks_for_pr(repo_config, pr_number, "PRE_CHECKS")


def get_extra_checks(repo_config: types.ModuleType, pr_number: int) -> List[str]:
    """
    Get EXTRA_CHECKS categories for a PR.

    EXTRA_CHECKS are signatures that:
    - Reset on every new commit
    - Are required before merging

    Args:
        repo_config: Repository configuration module
        pr_number: PR number

    Returns:
        List of category names required for merge
    """
    return get_checks_for_pr(repo_config, pr_number, "EXTRA_CHECKS")


def is_extra_check_category(repo_config: types.ModuleType, pr_number: int, category: str) -> bool:
    """
    Check if a category is an EXTRA_CHECK (or PRE_CHECK) category.

    These categories reset on every commit.

    Args:
        repo_config: Repository configuration module
        pr_number: PR number
        category: Category name to check

    Returns:
        True if category is a PRE_CHECK or EXTRA_CHECK
    """
    pre_checks = get_pre_checks(repo_config, pr_number)
    extra_checks = get_extra_checks(repo_config, pr_number)
    return category in pre_checks or category in extra_checks


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
        handler: Function to execute when command matches
        acl: Access control (list of allowed users, L2 categories, or callback)
        description: Human-readable description
        pr_only: If True, command is only valid for PRs (not issues)
    """

    name: str
    pattern: re.Pattern
    handler: Callable[..., bool]
    acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None
    description: str = ""
    pr_only: bool = False


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
            )
        )

    def command(
        self,
        name: str,
        pattern: str,
        acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
        description: str = "",
        pr_only: bool = False,
    ) -> Callable[[Callable[..., bool]], Callable[..., bool]]:
        r"""
        Decorator to register a command handler.

        Usage:
            @registry.command("approve", r"^\+1$|^\+(\w+)$", description="Approve PR")
            def handle_approve(context, match, user, comment_id, timestamp) -> bool:
                # ... handler logic ...
                return True  # Success

        Args:
            name: Command identifier
            pattern: Regex pattern to match
            acl: Access control specification
            description: Human-readable description
            pr_only: If True, command only applies to PRs

        Returns:
            Decorator function
        """

        def decorator(func: Callable[..., bool]) -> Callable[..., bool]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> bool:
                return func(*args, **kwargs)

            self.register(name, pattern, wrapper, acl, description, pr_only)
            return wrapper

        return decorator

    def find_command(self, text: str, is_pr: bool = True) -> Optional[Tuple[Command, re.Match]]:
        """
        Find a command matching the given text.

        Args:
            text: Command text to match
            is_pr: True if this is a PR, False if it's an Issue

        Returns:
            Tuple of (Command, Match) or None
        """
        for cmd in self.commands:
            # Skip PR-only commands when processing issues
            if cmd.pr_only and not is_pr:
                continue
            match = cmd.pattern.match(text)
            if match:
                return cmd, match
        return None


# Global command registry - commands register themselves via decorators
_global_registry = CommandRegistry()


def command(
    name: str,
    pattern: str,
    acl: Optional[Union[Iterable[str], Callable[..., bool]]] = None,
    description: str = "",
    pr_only: bool = False,
) -> Callable[[Callable[..., bool]], Callable[..., bool]]:
    r"""
    Module-level decorator to register commands.

    Usage:
        @command("approve", r"^\+1$|^\+(\w+)$", description="Approve PR", pr_only=True)
        def handle_approve(context, match, user, comment_id, timestamp) -> bool:
            return True
    """
    return _global_registry.command(name, pattern, acl, description, pr_only)


def get_global_registry() -> CommandRegistry:
    """Get the global command registry."""
    return _global_registry


# =============================================================================
# COMMAND PREPROCESSING
# =============================================================================


def preprocess_command(line: str) -> str:
    """
    Preprocess a command line according to specification.

    - Normalize whitespace
    - Remove spaces around commas
    - Strip leading/trailing whitespace
    - Remove @cmsbuild and 'please' prefixes
    """
    # Normalize whitespace
    line = " ".join(line.split())

    # Remove spaces around commas
    line = re.sub(r"\s*,\s*", ",", line)

    # Strip leading/trailing whitespace
    line = line.strip()

    # Remove prefixes
    line = re.sub(r"^(@?cmsbuild\s?[,]*\s?)?(please\s?[,]*\s?)?", "", line, flags=re.IGNORECASE)

    return line


def extract_command_line(comment_body: str) -> Optional[str]:
    """Extract the first non-blank line from a comment for command parsing."""
    if not comment_body:
        return None

    for line in comment_body.split("\n"):
        stripped = line.strip()
        if stripped:
            return preprocess_command(stripped)
    return None


# =============================================================================
# PR DESCRIPTION PARSING
# =============================================================================


def should_ignore_pr(pr_body: str) -> bool:
    """
    Check if PR should be ignored based on description.

    Returns True if first non-blank line matches <cms-bot></cms-bot>.
    """
    first_line = extract_command_line(pr_body or "")
    if not first_line:
        return False
    return bool(RE_CMS_BOT_IGNORE.match(first_line))


def should_notify_without_at(pr_body: str) -> bool:
    """
    Check if notifications should omit @ symbol.

    Returns True if first non-blank line matches <notify></notify>.
    """
    first_line = extract_command_line(pr_body or "")
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
    packages: Set[str] = field(default_factory=set)  # Packages touched by PR
    test_params: Dict[str, str] = field(default_factory=dict)  # Parameters from 'test parameters:'
    granted_test_rights: Set[str] = field(default_factory=set)  # Users granted test rights

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

    # Welcome message tracking
    welcome_message_posted: bool = False  # True if welcome message was posted

    # Watchers for this PR
    watchers: Set[str] = field(default_factory=set)  # Users watching files/categories

    # Changed files (cached)
    _changed_files: Optional[List[str]] = field(default=None, repr=False)

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
    Post a bot comment, avoiding duplicates.

    Checks if a message with the same key (tied to a comment_id if provided)
    has already been posted. If so, skips posting.

    Args:
        context: PR processing context
        message: The message to post
        message_key: Unique key identifying the message type
        comment_id: Optional comment ID this message is in response to

    Returns:
        True if message was posted, False if skipped (duplicate or dry run)
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

    # Mark as posted
    context.posted_messages.add(full_key)

    # Add invisible marker to message for future detection
    marked_message = f"{message}\n<!--{full_key}-->"

    if context.dry_run:
        logger.info(f"[DRY RUN] Would post comment: {message[:100]}...")
        return False

    try:
        context.issue.create_comment(marked_message)
        logger.info(f"Posted comment: {message_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        return False


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
) -> bool:
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
) -> bool:
    """Handle -1 or -<category> rejection."""
    return _handle_approval(context, match, user, comment_id, timestamp, approved=False)


def _handle_approval(
    context: PRContext,
    match: re.Match,
    user: str,
    comment_id: int,
    timestamp: datetime,
    approved: bool,
) -> bool:
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
        True if approval was recorded, False otherwise
    """
    category_str = match.group(1) if match.lastindex and match.group(1) else None

    # Determine which categories this signature applies to
    if category_str:
        # Specific category
        categories = [category_str.strip()]
    else:
        # Generic +1/-1 applies to all user's L2 categories at that time
        categories = get_user_l2_categories(context.repo_config, user, timestamp)

    if not categories:
        logger.info(f"User {user} has no L2 categories to sign with")
        return False

    # Determine which snapshot this signature should be associated with
    # This depends on which commits were present at the time of the comment
    snapshot_id = get_snapshot_for_timestamp(context, timestamp)

    # Update comment info in cache
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line="+1" if approved else "-1",
        ctype="+1" if approved else "-1",
        categories=categories,
        snapshot=snapshot_id,
        user=user,
        locked=False,  # Not locked until a commit happens after
    )
    context.cache.comments[str(comment_id)] = comment_info

    logger.info(
        f"Recorded {'approval' if approved else 'rejection'} from {user} "
        f"for categories: {categories} (snapshot={snapshot_id})"
    )
    return True


@command(
    "assign_category",
    rf"^assign\s+(?P<categories>(?:{CATEGORY_PATTERN})(?:,(?:{CATEGORY_PATTERN}))*)$",
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
    r"^assign\s+from\s+(?P<packages>[\w/,-]+(?:,[\w/,-]+)*)$",
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

        # Get L2s for the new categories
        new_l2s = set()
        for cat in new_categories:
            cat_l2s = get_category_l2s(context.repo_config, cat, timestamp)
            new_l2s.update(cat_l2s)

        # Post message about new categories
        if new_l2s:
            l2_mentions = ",".join(format_mention(context, l2) for l2 in sorted(new_l2s))
            msg = (
                f"New categories assigned: {','.join(new_categories)}\n\n"
                f"{l2_mentions} you have been requested to review this Pull request/Issue "
                "and eventually sign? Thanks"
            )
            post_bot_comment(context, msg, "assign", comment_id)

    logger.info(f"Assigned categories: {', '.join(categories)}")
    return True


@command(
    "unassign_category",
    rf"^unassign\s+(?P<categories>(?:{CATEGORY_PATTERN})(?:,(?:{CATEGORY_PATTERN}))*)$",
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
    r"^unassign\s+from\s+(?P<packages>[\w/,-]+(?:,[\w/,-]+)*)$",
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

    # Remove categories from signing_categories
    for cat in categories:
        context.signing_categories.discard(cat)

    logger.info(f"Unassigned categories: {', '.join(categories)}")
    return True


@command("hold", r"^hold$", description="Place a hold to prevent automerge", pr_only=True)
def handle_hold(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """Handle hold command - prevents automerge."""
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)

    if not user_categories:
        logger.info(f"User {user} has no L2 categories, cannot place hold")
        return False

    # Place hold for each of the user's categories
    for category in user_categories:
        hold = Hold(category=category, user=user, comment_id=comment_id)
        context.holds.append(hold)
        logger.info(f"Hold placed by {user} ({category})")

    # Post hold notification
    msg = (
        f"Pull request has been put on hold by {format_mention(context, user)}\n"
        "They need to issue an `unhold` command to remove the `hold` state "
        "or L1 can `unhold` it for all"
    )
    post_bot_comment(context, msg, "hold", comment_id)

    # Note: hold commands are not cached - only signatures (+1/-1) are cached
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

    - L2 member can remove holds from their own category
    - ORP can remove ALL holds
    """
    user_categories = get_user_l2_categories(context.repo_config, user, timestamp)
    is_orp = "orp" in [c.lower() for c in user_categories]

    if is_orp:
        # ORP unhold removes ALL holds
        removed_count = len(context.holds)
        context.holds = []
        logger.info(f"ORP user {user} removed all {removed_count} holds")
        success = removed_count > 0 or True  # ORP unhold always succeeds
    else:
        # Remove only holds from user's categories
        original_count = len(context.holds)
        context.holds = [h for h in context.holds if h.category not in user_categories]
        removed = original_count - len(context.holds)
        if removed > 0:
            logger.info(f"User {user} removed {removed} hold(s) from their categories")
            success = True
        else:
            logger.info(f"User {user} had no holds to remove")
            success = False

    # Note: unhold commands are not cached - only signatures (+1/-1) are cached
    return success


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
    r"^abort(?:\s+test)?$",
    acl=is_valid_tester,
    description="Abort pending tests",
    pr_only=True,
)
def handle_abort(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle abort/abort test command.

    Aborts any pending tests for the PR.
    """
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
    r"^backport\s+(?:of\s+)?(?:#|https?://github\.com/[^/]+/[^/]+/pull/)(?P<pr_num>\d+)$",
    description="Mark PR as backport of another PR",
)
def handle_backport(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle backport of #<num> command.

    Can be used by L2s, release managers, or the PR author.
    """
    pr_num = match.group("pr_num")
    context.pending_labels.add("backport")
    context.backport_of = pr_num
    logger.info(f"PR marked as backport of #{pr_num} by {user}")
    return True


@command(
    "allow_test_rights",
    r"^allow\s+@(?P<username>[^\s]+)\s+test\s+rights$",
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
    r"^code-checks(?:\s+with\s+(?P<tool_conf>\S+))?(?:\s+and\s+apply\s+patch)?$",
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
    r"^ignore\s+tests-rejected\s+(?:with\s+)?(?P<reason>manual-override|ib-failure|external-failure)$",
    description="Override test failure with reason",
    pr_only=True,
)
def handle_ignore_tests_rejected(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle 'ignore tests-rejected with <reason>' command.

    Allows overriding a test failure with a valid reason.
    Valid reasons: manual-override, ib-failure, external-failure
    """
    reason = match.group("reason")
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
    r"^type\s+(?P<label>[\w-]+)$",
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
)
def handle_build_test(
    context: PRContext, match: re.Match, user: str, comment_id: int, timestamp: datetime
) -> bool:
    """
    Handle build/test command.

    Syntax:
        build|test [workflows <wf_list>] [with <pr_list>] [for <queue>]
                   [using [full cmssw] [addpkg <pkg_list>]]

    Examples:
        test
        build workflows 1.0,2.0
        test with cms-sw/cmssw#12345
        build for rhel8-amd64
        test using full cmssw
        build using addpkg RecoTracker/PixelSeeding

    The test will only be triggered if all required signatures (categories)
    specified in PRE_CHECKS are approved.

    Values from 'test parameters:' command are used as defaults, but values
    specified directly in this command override them.
    """
    # Get the full command line from the comment
    first_line = match.group(0)

    # Try to get full first line from the actual comment (use cached comments)
    for comment in context.comments:
        if comment.id == comment_id:
            first_line = extract_command_line(comment.body or "") or first_line
            break

    try:
        result = parse_test_cmd(first_line)
    except TestCmdParseError as e:
        logger.warning(f"Invalid build/test command: {e}")
        context.messages.append(f"Invalid build/test command: {e}")
        return False

    # Check if required signatures (PRE_CHECKS) are present
    pr_number = context.issue.number if context.issue else 0
    required_categories = get_pre_checks(context.repo_config, pr_number)
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

    # Note: build/test commands are not cached - only signatures (+1/-1) are cached
    return True


# =============================================================================
# FILE STATE MANAGEMENT
# =============================================================================


def get_pr_files(pr) -> Dict[str, str]:
    """
    Get all files in the PR with their blob SHAs.

    Returns:
        Dict mapping filename to blob_sha
    """
    files = {}
    for f in pr.get_files():
        # For deleted files, sha might be None
        if f.sha:
            files[f.filename] = f.sha
    return files


def get_changed_files(repo, pr) -> List[str]:
    """
    Get list of changed file names in a PR.

    Unlike get_pr_files, this returns only filenames (not SHAs) and includes
    the previous filename for renamed files.

    Args:
        repo: Repository object
        pr: Pull request object

    Returns:
        List of changed file paths (including old names for renames)
    """
    changed_files = []
    for f in pr.get_files():
        changed_files.append(f.filename)
        # Include previous filename for renamed files
        if f.previous_filename:
            changed_files.append(f.previous_filename)
    return changed_files


def update_file_states(context: PRContext) -> Set[str]:
    """
    Update file states based on current PR state.

    Creates a new snapshot if files changed.

    Returns:
        Set of filenames that changed since last check
    """
    current_files = get_pr_files(context.pr)
    changed_files = set()
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

    # Build list of current file version keys
    current_fv_keys = []

    for filename, blob_sha in current_files.items():
        fv_key = f"{filename}::{blob_sha}"
        current_fv_keys.append(fv_key)

        if fv_key not in context.cache.file_versions:
            # New file version
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

    # Check for files that were removed (in old snapshot but not current)
    current_snapshot = context.cache.get_current_snapshot()
    if current_snapshot:
        old_files = set()
        for fv_key in current_snapshot.changes:
            if "::" in fv_key:
                filename = fv_key.split("::")[0]
                old_files.add(filename)

        for filename in old_files:
            if filename not in current_files:
                changed_files.add(filename)

    # Create new snapshot if there are changes or no current snapshot
    if changed_files or not current_snapshot:
        # Generate new snapshot ID
        snapshot_id = str(len(context.cache.snapshots) + 1)

        context.cache.snapshots[snapshot_id] = Snapshot(
            snapshot_id=snapshot_id,
            timestamp=now,
            changes=current_fv_keys,
        )
        context.cache.current_snapshot_id = snapshot_id
        logger.debug(f"Created snapshot {snapshot_id} with {len(current_fv_keys)} files")

    return changed_files


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


def is_bot_allowed_command(command_line: str) -> bool:
    """
    Check if a command is allowed to be processed from bot's own comments.

    Some commands (like code-checks results, CI results) are posted by the bot
    itself or by external processes using the bot account, and should still be
    processed.

    Args:
        command_line: The preprocessed command line

    Returns:
        True if this command can be processed from bot comments
    """
    for pattern in BOT_ALLOWED_COMMAND_PATTERNS:
        if re.match(pattern, command_line, re.IGNORECASE):
            return True
    return False


def should_process_comment(
    context: PRContext, comment, command_line: Optional[str] = None
) -> bool:
    """
    Determine if a comment should be processed.

    Skip comments:
    - Already processed (based on comment ID in cache)
    - From the bot itself, UNLESS it's a bot-allowed command

    Args:
        context: PR processing context
        comment: The comment object
        command_line: Optional pre-extracted command line (for bot-allowed check)

    Returns:
        True if comment should be processed
    """
    # Skip already processed comments
    if str(comment.id) in context.cache.comments:
        return False

    # Check if this is from the bot
    is_bot_comment = context.cmsbuild_user and comment.user.login == context.cmsbuild_user

    if is_bot_comment:
        # Bot comments are only processed for specific allowed commands
        if command_line is None:
            command_line = extract_command_line(comment.body or "")

        if command_line and is_bot_allowed_command(command_line):
            logger.debug(
                f"Processing bot's own comment {comment.id} for allowed command: {command_line}"
            )
            return True

        return False

    return True


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


def process_comment(context: PRContext, comment) -> None:
    """Process a single comment for commands."""
    # Extract command line first (needed for bot-allowed check)
    command_line = extract_command_line(comment.body or "")

    if not should_process_comment(context, comment, command_line):
        return

    if not command_line:
        return

    result = context.command_registry.find_command(command_line, is_pr=context.is_pr)
    if not result:
        return

    cmd, match = result
    user = comment.user.login
    timestamp = get_comment_timestamp(comment)
    comment_id = comment.id

    # Check ACL
    if not check_command_acl(context, cmd, user, timestamp):
        logger.info(f"User {user} not authorized for command: {cmd.name}")
        # Set -1 reaction for unauthorized
        set_comment_reaction(context, comment, comment_id, success=False)
        return

    # Execute command - handler returns bool indicating success
    logger.info(f"Executing command '{cmd.name}' from user {user}")
    try:
        success = cmd.handler(context, match, user, comment_id, timestamp)
        if success is None:
            success = True  # Default to success if handler doesn't return
    except Exception as e:
        logger.error(f"Command handler error: {e}")
        success = False

    # Set reaction based on success
    set_comment_reaction(context, comment, comment_id, success=success)


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


def get_snapshot_for_timestamp(context: PRContext, timestamp: datetime) -> Optional[str]:
    """
    Get or create the appropriate snapshot ID for a signature at a given timestamp.

    Snapshots correspond to distinct states of the PR (sets of file versions).
    A new snapshot is created when commits change the PR state.

    For efficiency, we use the last commit timestamp before the comment as a key
    to determine which snapshot the signature belongs to.

    Args:
        context: PR processing context
        timestamp: Timestamp of the signature comment (should be tz-aware)

    Returns:
        Snapshot ID for this timestamp, or None if no snapshot exists
    """
    # Ensure timestamp is tz-aware
    timestamp = ensure_tz_aware(timestamp)

    # Get commit timestamps (already tz-aware from get_commit_timestamps)
    commit_timestamps = get_commit_timestamps(context) if context.is_pr else []

    if not commit_timestamps:
        # No commits, use current snapshot
        snapshot = context.cache.get_current_snapshot()
        return snapshot.snapshot_id if snapshot else None

    # Find the last commit before this timestamp
    last_commit = get_last_commit_before(commit_timestamps, timestamp)

    if last_commit is None:
        # Comment is before all commits - this shouldn't happen normally
        # but use the first snapshot if available
        if context.cache.snapshots:
            return list(context.cache.snapshots.keys())[0]
        return None

    # Check if we already have a snapshot for this commit
    for snap_id, snapshot in context.cache.snapshots.items():
        snap_ts = parse_timestamp(snapshot.timestamp)
        if snap_ts and abs((snap_ts - last_commit).total_seconds()) < 1:
            # Found matching snapshot (within 1 second tolerance)
            return snap_id

    # If no matching snapshot found, return current snapshot
    # (the snapshot system creates one snapshot for the current state,
    # and signatures are associated with it based on commit timing)
    snapshot = context.cache.get_current_snapshot()
    return snapshot.snapshot_id if snapshot else None


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
            current_first_line = extract_command_line(comment.body or "") or ""
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


def get_categories_from_snapshot(context: PRContext) -> Dict[str, Set[str]]:
    """
    Get all categories and their associated file version keys from current snapshot.

    Categories come from multiple sources:
    1. Automatic assignment: file → package → categories (stored in FileVersion.categories)
    2. Manual assignment: 'assign'/'unassign' commands (stored in context.signing_categories)
    3. PRE_CHECKS: Categories required before tests (from repo_config)
    4. EXTRA_CHECKS: Categories required for merge (from repo_config)

    Returns:
        Dict mapping category name to set of file version keys
    """
    categories: Dict[str, Set[str]] = {}
    snapshot = context.cache.get_current_snapshot()

    if not snapshot:
        return categories

    # Get categories from file versions (automatic assignment)
    for fv_key in snapshot.changes:
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
        categories[cat].update(snapshot.changes)

    # Add PRE_CHECKS and EXTRA_CHECKS categories
    # These are required signatures that apply to all files
    pr_number = context.issue.number if context.issue else 0
    pre_checks = get_pre_checks(context.repo_config, pr_number)
    extra_checks = get_extra_checks(context.repo_config, pr_number)

    for cat in pre_checks + extra_checks:
        if cat not in categories:
            categories[cat] = set()
        # These categories apply to all files in the snapshot
        categories[cat].update(snapshot.changes)

    return categories


def compute_category_approval_states(context: PRContext) -> Dict[str, ApprovalState]:
    """
    Compute approval state for each category based on signatures.

    Returns:
        Dict mapping category name to approval state
    """
    categories = get_categories_from_snapshot(context)
    snapshot = context.cache.get_current_snapshot()
    snapshot_id = snapshot.snapshot_id if snapshot else None

    category_states: Dict[str, ApprovalState] = {}

    for cat_name in categories:
        # Find signatures for this category that match current snapshot
        approved = False
        rejected = False

        for comment_id, comment_info in context.cache.comments.items():
            if comment_info.ctype not in ("+1", "-1"):
                continue
            if cat_name not in comment_info.categories:
                continue
            if comment_info.snapshot != snapshot_id:
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
    pr_number = context.issue.number if context.issue else 0

    # Get required checks
    pre_checks = get_pre_checks(context.repo_config, pr_number)
    extra_checks = get_extra_checks(context.repo_config, pr_number)

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
    pr_number = context.issue.number if context.issue else 0
    extra_checks = get_extra_checks(context.repo_config, pr_number)

    if "orp" in [c.lower() for c in extra_checks]:
        category_states = compute_category_approval_states(context)
        orp_state = category_states.get("orp", ApprovalState.PENDING)
        if orp_state != ApprovalState.APPROVED:
            return False

    return True


# =============================================================================
# STATUS REPORTING
# =============================================================================


def generate_status_message(context: PRContext) -> str:
    """Generate a status message for the PR or Issue."""
    lines = []
    entity_type = "PR" if context.is_pr else "Issue"

    if context.is_pr:
        pr_state = determine_pr_state(context)
        lines.append(f"**{entity_type} Status: {pr_state.value}**\n")
    else:
        lines.append(f"**{entity_type} Status**\n")

    # Category status (for PRs)
    if context.is_pr:
        category_states = compute_category_approval_states(context)
        pr_number = context.issue.number if context.issue else 0
        pre_checks = get_pre_checks(context.repo_config, pr_number)
        extra_checks = get_extra_checks(context.repo_config, pr_number)

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


def update_pr_status(context: PRContext) -> None:
    """Update PR/Issue labels and status based on current state."""
    if context.dry_run:
        logger.info("[DRY RUN] Would update PR/Issue status")
        return

    # Get current labels
    current_labels = {label.name for label in context.issue.get_labels()}
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

        # Remove old state labels, add current
        for state, label in state_labels.items():
            if state == pr_state:
                if label not in current_labels:
                    labels_to_add.add(label)
            else:
                if label in current_labels:
                    labels_to_remove.add(label)

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
            if current_state_label not in current_labels:
                labels_to_add.add(current_state_label)

            # Remove other state labels for this category
            for other_state, suffix in state_suffixes.items():
                if other_state != state:
                    old_label = f"{cat}{suffix}"
                    if old_label in current_labels:
                        labels_to_remove.add(old_label)

        # Add auto-labels based on file patterns
        auto_labels = get_labels_for_pr(context)
        for label in auto_labels:
            if label not in current_labels:
                labels_to_add.add(label)

    # Handle type labels from 'type' command (works for both PRs and Issues)
    # First, handle 'type' labels (only one allowed) - remove old ones
    for label in current_labels:
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
        if label not in current_labels:
            labels_to_add.add(label)

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
                if not dryRun:
                    context.issue.create_comment(msg)
                logger.warning(f"PR blocked: too many commits ({commit_count})")

            # Always block at FAIL threshold - cannot be overridden
            context.blocked_by_commit_count = True
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
                if not dryRun:
                    context.issue.create_comment(msg)
                logger.warning(f"PR warned: many commits ({commit_count})")

            # Block if not overridden
            if not context.ignore_commit_count:
                context.blocked_by_commit_count = True
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
                if not dryRun:
                    context.issue.create_comment(msg)
                logger.warning(f"PR blocked: too many files ({file_count})")

            # Always block at FAIL threshold - cannot be overridden
            context.blocked_by_file_count = True
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
                if not dryRun:
                    context.issue.create_comment(msg)
                logger.warning(f"PR warned: many files ({file_count})")

            # Block if not overridden
            if not context.ignore_file_count:
                context.blocked_by_file_count = True
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

    For CMSSW repo PRs, includes:
    - Package list with categories
    - New package warning if applicable
    - Patch branch warning if applicable
    - Release managers notification

    Args:
        context: PR processing context
    """
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

    # Build backport message
    backport_msg = ""
    if context.backport_of:
        backport_msg = f"Backported from #{context.backport_of}\n"

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
        resign_msg = f"\n{signers} can you please check and sign again."

    # Build watchers message
    watchers_msg = ""
    if context.watchers:
        watcher_mentions = ", ".join(format_mention(context, w) for w in sorted(context.watchers))
        watchers_msg = f"\n\n{watcher_mentions} this is something you requested to watch as well."

    msg = f"Pull request #{pr_number} was updated.{resign_msg}{watchers_msg}"
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
    if not force and should_ignore_pr(body):
        entity_type = "PR" if is_pr else "Issue"
        logger.info(f"{entity_type} has <cms-bot></cms-bot> tag, skipping processing")
        return {
            "pr_number": issue.number,
            "skipped": True,
            "reason": "cms-bot ignore tag",
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
    repository = context.repo_name  # Alias for compatibility

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
        if context.cmssw_repo or not context.external_repo:
            if context.cmssw_repo:
                # Add code-checks for master or forward-port branches
                fwports = forward_ports_map.GIT_REPO_FWPORTS.get("cmssw", {})
                if pr.base.ref == "master" or pr.base.ref in fwports.get(CMSSW_DEVEL_BRANCH, []):
                    context.signing_categories.add("code-checks")
                update_milestone(repo, issue, pr, dryRun)

            chg_files = get_changed_files(repo, pr)
            context._changed_files = chg_files
            context.packages = set(file_to_package(repo_config, f) for f in chg_files)
            add_nonblocking_labels(chg_files, context.pending_labels)
            context.create_test_property = True
        else:
            # External repo handling
            context.packages = {f"externals/{repository}"}
            ex_pkg = external_to_package(repository)
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
                    chg_files = get_changed_files(repo, pr)
                    context._changed_files = chg_files
                    add_nonblocking_labels(chg_files, context.pending_labels)
            except Exception:
                pass

        # Load watchers based on changed files and categories
        if chg_files:
            context.watchers = get_watchers(context, chg_files, datetime.now(tz=timezone.utc))

        # Update file states (creates snapshot)
        changed_files = update_file_states(context)
        if changed_files:
            logger.info(f"Changed files: {changed_files}")

        # Check for new commits and post update message if needed
        check_for_new_commits(context)

    # Process all comments
    process_all_comments(context)

    # Check commit and file counts (for PRs only)
    if is_pr and pr:
        block_result = check_commit_and_file_counts(context, dryRun)
        if block_result:
            # Save cache before returning
            save_cache_to_comments(issue, context.comments, cache, dryRun)
            return block_result

    # Update status (labels, etc.) for both PRs and Issues
    update_pr_status(context)

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
        if context.abort_tests:
            logger.info("Creating abort test properties file")
            create_abort_properties(context)

        # Trigger tests if requested
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
    else:
        # Issue-specific processing
        # Check if issue is fully signed
        category_states = compute_category_approval_states(context)
        all_approved = (
            all(state == ApprovalState.APPROVED for state in category_states.values())
            if category_states
            else False
        )

        if all_approved and category_states:
            post_bot_comment(
                context,
                "This issue is fully signed and ready to be closed.",
                "issue_fully_signed",
            )
        # Check for new data repo request issues
        if context.cmssw_repo and re.match(CREATE_REPO, issue.title or ""):
            logger.info(f"Creating new data repo properties for issue #{issue.number}")
            create_new_data_repo_properties(issue.number, dryRun)

    # Save cache
    save_cache_to_comments(issue, context.comments, cache, dryRun)

    # Generate status message (for both PRs and Issues)
    status_message = generate_status_message(context)

    # Compute category states for return value (for PRs)
    category_states = compute_category_approval_states(context) if is_pr else {}

    # Get check types for result
    pre_checks = get_pre_checks(repo_config, issue.number)
    extra_checks = get_extra_checks(repo_config, issue.number)

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
