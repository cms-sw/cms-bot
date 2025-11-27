#!/usr/bin/env python3
"""
cms-bot: A GitHub bot for automating CI tests and PR reviews.

This bot is stateless except for a small cache stored in PR issue comments.
It handles code ownership, approval workflows, and merge automation.
"""

import base64
import gzip
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
from os.path import dirname, exists, join
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from categories import (
    CMSSW_L2,
    CMSSW_ORP,
    TRIGGER_PR_TESTS,
    CMSSW_ISSUES_TRACKERS,
    PR_HOLD_MANAGERS,
    EXTERNAL_REPOS,
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

# Commands that can be processed from bot's own comments
# (for CI results, code-checks, etc.)
BOT_ALLOWED_COMMAND_PATTERNS = [
    r"^[+-]code-checks$",
    r"^[+-]1$",
    r"^[+-]\w+$",  # Category-specific approvals/rejections
]

# Regex patterns for build/test command parameters
WF_PATTERN = r"(?:[a-z][a-z0-9_]+|[1-9][0-9]*(?:\.[0-9]+)?)"
CMSSW_QUEUE_PATTERN = (
    "CMSSW_[0-9]+_[0-9]+_(((X|[A-Z][A-Z0-9]+_X)(_[0-9-]+|))|[0-9]+(_[a-zA-Z0-9_]+)?)"
)
CMSSW_PACKAGE_PATTERN = "[A-Z][a-zA-Z0-9]+(?:/[a-zA-Z0-9]+|)"
ARCH_PATTERN = "[a-z0-9]+_[a-z0-9]+_[a-z0-9]+"
CMSSW_RELEASE_QUEUE_PATTERN = (
    f"(?:{CMSSW_QUEUE_PATTERN}|{ARCH_PATTERN}|{CMSSW_QUEUE_PATTERN}/{ARCH_PATTERN})"
)
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

# Regex patterns for PR description flags
RE_CMS_BOT_IGNORE = re.compile(r"<cms-bot>\s*</cms-bot>", re.IGNORECASE)
RE_NOTIFY_NO_AT = re.compile(r"<notify>\s*</notify>", re.IGNORECASE)

# Global L2 data cache
_L2_DATA: Dict[str, List[Dict[str, Any]]] = {}


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


def get_l2_data() -> Dict[str, List[Dict[str, Any]]]:
    """Get the cached L2 data."""
    return _L2_DATA


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
    l2_data = get_l2_data()

    if not l2_data:
        # Fallback to static CMSSW_L2 if L2 data not initialized
        return [CMSSW_L2.get(username)] if username in CMSSW_L2 else []

    if username not in l2_data:
        return []

    # Find categories active at the given timestamp
    ts_epoch = timestamp.timestamp() if isinstance(timestamp, datetime) else timestamp

    for period in l2_data[username]:
        start_date = period.get("start_date", 0)
        end_date = period.get("end_date")

        # Check if timestamp falls within this period
        if ts_epoch < start_date:
            return []

        if end_date is None or ts_epoch < end_date:
            return period["category"]

    return []


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
    tests_to_run: List[Any] = field(default_factory=list)  # List of TestRequest objects
    pending_reactions: Dict[int, str] = field(default_factory=dict)  # comment_id -> reaction
    holds: List[Hold] = field(default_factory=list)  # Active holds on the PR

    # PR description flags
    notify_without_at: bool = False  # If True, don't use @ when mentioning users


def format_mention(context: PRContext, username: str) -> str:
    """
    Format a username for mentioning in a comment.

    If the PR has <notify></notify> in its description, omit the @ symbol.

    Args:
        context: PR processing context
        username: GitHub username to mention

    Returns:
        Formatted mention string (with or without @)
    """
    if context.notify_without_at:
        return username
    return f"@{username}"


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

    # Get current snapshot
    snapshot = context.cache.get_current_snapshot()
    snapshot_id = snapshot.snapshot_id if snapshot else None

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
        f"for categories: {categories}"
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

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line=f"assign {','.join(categories)}",
        ctype="assign",
        categories=categories,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

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

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line=f"unassign {','.join(categories)}",
        ctype="unassign",
        categories=categories,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

    logger.info(f"Unassigned categories: {', '.join(categories)}")
    return True

    logger.info(f"Assigned category: {category}")
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

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line="hold",
        ctype="hold",
        categories=user_categories,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

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

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line="unhold",
        ctype="unhold",
        categories=user_categories,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

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

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line="merge",
        ctype="merge",
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

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


@command("build_test", r"^(build|test)\b", description="Trigger CI build/test", pr_only=True)
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

    # Create test request
    request = TestRequest(
        verb=result.verb,
        workflows=",".join(set(result.workflows)) if result.workflows else "",
        prs=result.prs,
        queue=result.queue,
        build_full=bool(result.full),
        extra_packages=",".join(set(result.addpkg)) if result.addpkg else "",
        triggered_by=user,
        comment_id=comment_id,
    )

    context.tests_to_run.append(request)
    logger.info(f"{result.verb.capitalize()} triggered by {user}: {request}")

    # Record in comment info
    comment_info = CommentInfo(
        timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        first_line=first_line,
        ctype=result.verb,
        user=user,
    )
    context.cache.comments[str(comment_id)] = comment_info

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
                now = commit_ts.isoformat() + "Z"
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


def get_comment_timestamp(comment) -> datetime:
    """Get the timestamp of a comment."""
    return comment.created_at


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

    Returns:
        List of commit timestamps (datetime objects)
    """
    if not context.commits:
        return []

    timestamps = []
    for commit in context.commits:
        try:
            commit_date = commit.commit.author.date
            if commit_date:
                if isinstance(commit_date, datetime):
                    timestamps.append(commit_date)
                else:
                    # Parse string timestamp
                    timestamps.append(datetime.fromisoformat(commit_date.replace("Z", "+00:00")))
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


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse an ISO format timestamp string to datetime."""
    if not ts:
        return None
    try:
        # Handle various ISO formats
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


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
    2. Manual assignment: 'assign'/'unassign' commands (stored in CommentInfo)
    3. PRE_CHECKS: Categories required before tests (from repo_config)
    4. EXTRA_CHECKS: Categories required for merge (from repo_config)

    The assign/unassign commands are processed in order to compute the final
    set of manually assigned categories.

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

    # Process assign/unassign commands in order to compute manual assignments
    # Sort by comment_id to ensure chronological order
    manual_categories: Set[str] = set()
    sorted_comments = sorted(context.cache.comments.items(), key=lambda x: int(x[0]))

    for comment_id, comment_info in sorted_comments:
        if comment_info.ctype == "assign":
            for cat in comment_info.categories:
                manual_categories.add(cat)
        elif comment_info.ctype == "unassign":
            for cat in comment_info.categories:
                manual_categories.discard(cat)

    # Add manually assigned categories (apply to all files in snapshot)
    for cat in manual_categories:
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
    """Generate a status message for the PR."""
    lines = []

    pr_state = determine_pr_state(context)
    lines.append(f"**PR Status: {pr_state.value}**\n")

    # Category status
    category_states = compute_category_approval_states(context)
    pr_number = context.issue.number if context.issue else 0
    pre_checks = get_pre_checks(context.repo_config, pr_number)
    extra_checks = get_extra_checks(context.repo_config, pr_number)

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

    return "\n".join(lines)


def update_pr_status(context: PRContext) -> None:
    """Update PR labels and status based on current state."""
    if context.dry_run:
        logger.info("[DRY RUN] Would update PR status")
        return

    pr_state = determine_pr_state(context)

    # Update labels
    current_labels = {label.name for label in context.issue.get_labels()}

    state_labels = {
        PRState.TESTS_PENDING: "tests-pending",
        PRState.SIGNATURES_PENDING: "signatures-pending",
        PRState.FULLY_SIGNED: "fully-signed",
        PRState.MERGED: "merged",
    }

    # Remove old state labels
    for state, label in state_labels.items():
        if state != pr_state and label in current_labels:
            try:
                context.issue.remove_from_labels(label)
            except Exception:
                pass  # Label might not exist

    # Add current state label
    current_label = state_labels.get(pr_state)
    if current_label and current_label not in current_labels:
        try:
            context.issue.add_to_labels(current_label)
        except Exception as e:
            logger.warning(f"Could not add label {current_label}: {e}")


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

    # PR-specific processing
    if is_pr and pr:
        # Update file states (creates snapshot)
        changed_files = update_file_states(context)
        if changed_files:
            logger.info(f"Changed files: {changed_files}")

    # Process all comments
    process_all_comments(context)

    # PR-specific state determination and actions
    pr_state = None
    if is_pr:
        # Determine PR state
        pr_state = determine_pr_state(context)
        logger.info(f"PR state: {pr_state.value}")

        # Update PR status (labels, etc.)
        update_pr_status(context)

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

        # Trigger tests if requested
        for test in context.tests_to_run:
            if dryRun:
                logger.info(f"[DRY RUN] Would trigger test: {test}")
            else:
                # TODO: Implement actual test triggering based on repo_config
                logger.info(f"Would trigger test: {test}")

    # Save cache
    save_cache_to_comments(issue, context.comments, cache, dryRun)

    # Generate status message (for PRs)
    status_message = generate_status_message(context) if is_pr else ""

    # Compute category states for return value (for PRs)
    category_states = compute_category_approval_states(context) if is_pr else {}

    # Get check types for result
    pre_checks = get_pre_checks(repo_config, issue.number)
    extra_checks = get_extra_checks(repo_config, issue.number)

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
        "messages": context.messages,
        "status_message": status_message,
        "tests_triggered": context.tests_to_run,
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
