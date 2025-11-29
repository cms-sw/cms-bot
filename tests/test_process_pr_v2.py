#!/usr/bin/env python3
"""
PyTest tests for process_pr_v2 module.

This test module provides:
- Mock implementations of PyGithub classes that load state from JSON files
- Recording mode to capture actions for later comparison
- Comparison mode to verify actions match expected results

Usage:
    # Run tests in comparison mode (default)
    pytest test_process_pr_v2.py

    # Run tests in recording mode (saves actions to PRActionData/)
    pytest test_process_pr_v2.py --record-actions

    # Run a specific test
    pytest test_process_pr_v2.py::test_basic_approval --record-actions
"""

import json
import os
import sys
import types
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module under test
from process_pr_v2 import (
    PRContext,
    TestCmdParseError,
    TestRequest,
    TOO_MANY_COMMITS_FAIL_THRESHOLD,
    TOO_MANY_COMMITS_WARN_THRESHOLD,
    TOO_MANY_FILES_WARN_THRESHOLD,
    build_test_parameters,
    check_commit_and_file_counts,
    create_property_file,
    extract_command_line,
    format_mention,
    init_l2_data,
    is_valid_tester,
    parse_test_cmd,
    parse_test_parameters,
    parse_timestamp,
    preprocess_command,
    process_pr,
    should_ignore_issue,
    should_notify_without_at,
)

# Import BUILD_REL for testing ignore logic
try:
    from cms_static import BUILD_REL
except ImportError:
    # Fallback pattern if cms_static not available: ^[Bb]uild[ ]+(CMSSW_[^ ]+)
    BUILD_REL = r"^[Bb]uild[ ]+(CMSSW_[^ ]+)"


def create_mock_repo_config(**overrides) -> types.ModuleType:
    """
    Create a mock repo_config module for testing.

    Args:
        **overrides: Override any default configuration values

    Returns:
        A module-like object with configuration attributes
    """
    module = types.ModuleType("mock_repo_config")

    # Default configuration
    module.CONFIG_DIR = str(Path(__file__).parent)

    # File ownership patterns -> L2 categories
    module.FILE_OWNERS = {
        r"^src/core/.*": ["core"],
        r"^src/analysis/.*": ["analysis"],
        r"^src/simulation/.*": ["simulation"],
        r"^docs/.*": ["docs"],
        r"^tests/.*": ["testing"],
    }

    # Package -> category mapping (for 'assign from' command)
    module.PACKAGE_CATEGORIES = {
        "numpy": "analysis",
        "scipy": "analysis",
        "matplotlib": "visualization",
    }

    # PRE_CHECKS: Signatures required before running tests
    # List of (min_pr_number, [categories])
    # These reset on every commit
    module.PRE_CHECKS = [(0, ["code-checks"])]

    # EXTRA_CHECKS: Signatures required for merge
    # List of (min_pr_number, [categories])
    # These reset on every commit
    module.EXTRA_CHECKS = [(0, ["tests", "orp"])]

    # Automatically merge when fully signed
    module.AUTOMERGE = False

    # Apply overrides
    for key, value in overrides.items():
        setattr(module, key, value)

    return module


def setup_test_l2_data(user_categories: Dict[str, List[str]] = None) -> None:
    """
    Setup L2 data for testing by directly modifying the global _L2_DATA.

    Args:
        user_categories: Dict mapping username to list of categories
    """
    import process_pr_v2

    if user_categories is None:
        # Default test L2 data
        user_categories = {
            "alice": ["core", "analysis"],
            "bob": ["simulation"],
            "carol": ["docs", "testing"],
            "dave": ["orp"],
            "cmsbuild": ["tests", "code-checks"],
        }

    # Convert to L2 data format (list of periods)
    l2_data = {}
    for user, categories in user_categories.items():
        l2_data[user] = [{"start_date": 0, "category": categories}]

    process_pr_v2._L2_DATA = l2_data


@pytest.fixture(autouse=True)
def setup_l2_data():
    """Fixture to setup L2 data before each test."""
    setup_test_l2_data()
    yield
    # Cleanup after test
    import process_pr_v2

    process_pr_v2._L2_DATA = {}


@pytest.fixture(autouse=True)
def mock_cmssw_categories(monkeypatch):
    """Mock CMSSW_CATEGORIES with test categories."""
    test_categories = {
        "core": ["Package/Core", "Package/Framework"],
        "analysis": ["Package/Analysis", "numpy", "scipy"],
        "simulation": ["Package/Simulation"],
        "visualization": ["Package/Visualization", "matplotlib"],
        "docs": ["Package/Docs"],
        "testing": ["Package/Testing"],
        "orp": [],
        "tests": [],
        "code-checks": [],
        "reconstruction": ["Package/Reconstruction"],
        "l1": ["Package/L1"],
        "hlt": ["Package/HLT"],
        "db": ["Package/DB"],
        "dqm": ["Package/DQM"],
        "generators": ["Package/Generators"],
        "fastsim": ["Package/FastSim"],
        "fullsim": ["Package/FullSim"],
        "operations": ["Package/Operations"],
        "pdmv": ["Package/PdmV"],
        "upgrade": ["Package/Upgrade"],
        "geometry": ["Package/Geometry"],
        "alca": ["Package/Alca"],
        "ml": ["Package/ML"],
        "heterogeneous": ["Package/Heterogeneous"],
        "tracking": ["Package/Tracking"],
    }
    monkeypatch.setattr("process_pr_v2.CMSSW_CATEGORIES", test_categories)
    yield test_categories


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Base directories for test data
REPLAY_DATA_DIR = Path(__file__).parent / "ReplayData"
ACTION_DATA_DIR = Path(__file__).parent / "PRActionData"


# pytest_addoption and record_mode fixture are defined in conftest.py


# =============================================================================
# ACTION RECORDER
# =============================================================================


class ActionRecorder:
    """
    Records actions taken during PR processing for later verification.

    Actions are recorded as a list of dictionaries with:
    - action: The type of action (e.g., 'create_comment', 'add_label')
    - timestamp: When the action occurred
    - details: Action-specific data
    """

    def __init__(self, test_name: str, record_mode: bool = False):
        self.test_name = test_name
        self.record_mode = record_mode
        self.actions: List[Dict[str, Any]] = []
        self._action_counter = 0

    def record(self, action: str, **details) -> None:
        """Record an action."""
        self._action_counter += 1
        self.actions.append(
            {
                "sequence": self._action_counter,
                "action": action,
                "details": details,
            }
        )

    def save(self) -> None:
        """Save recorded actions to file."""
        ACTION_DATA_DIR.mkdir(parents=True, exist_ok=True)
        filepath = ACTION_DATA_DIR / f"{self.test_name}.json"

        with open(filepath, "w") as f:
            json.dump(
                {
                    "test_name": self.test_name,
                    "action_count": len(self.actions),
                    "actions": self.actions,
                },
                f,
                indent=2,
                default=str,
            )

        print(f"Saved {len(self.actions)} actions to {filepath}")

    def load_expected(self) -> List[Dict[str, Any]]:
        """Load expected actions from file."""
        filepath = ACTION_DATA_DIR / f"{self.test_name}.json"

        if not filepath.exists():
            raise FileNotFoundError(
                f"Expected action data not found: {filepath}\n"
                f"Run with --record-actions to create it."
            )

        with open(filepath) as f:
            data = json.load(f)

        return data.get("actions", [])

    def _action_key(self, action: Dict[str, Any]) -> str:
        """
        Create a hashable key for an action for comparison.

        The key is based on action type and sorted details.
        """
        details = action.get("details", {})
        # Sort details for consistent comparison
        sorted_details = tuple(sorted((k, str(v)) for k, v in details.items()))
        return f"{action['action']}:{sorted_details}"

    def _actions_match(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> bool:
        """
        Check if two actions match (same type and details).
        """
        if actual["action"] != expected["action"]:
            return False

        # Compare details
        exp_details = expected.get("details", {})
        act_details = actual.get("details", {})

        for key, exp_value in exp_details.items():
            actual_value = act_details.get(key)
            if actual_value != exp_value:
                return False

        return True

    def verify(self) -> None:
        """
        Verify recorded actions match expected (order-independent).

        Actions are compared as sets - same actions must be present
        but order doesn't matter.
        """
        expected = self.load_expected()

        # Compare action counts
        assert len(self.actions) == len(expected), (
            f"Action count mismatch: got {len(self.actions)}, "
            f"expected {len(expected)}\n"
            f"Actual actions: {[a['action'] for a in self.actions]}\n"
            f"Expected actions: {[a['action'] for a in expected]}"
        )

        # Build list of expected actions (mutable copy for matching)
        remaining_expected = list(expected)
        unmatched_actual = []

        # Try to match each actual action to an expected action
        for actual in self.actions:
            matched = False
            for i, exp in enumerate(remaining_expected):
                if self._actions_match(actual, exp):
                    remaining_expected.pop(i)
                    matched = True
                    break

            if not matched:
                unmatched_actual.append(actual)

        # If there are unmatched actions, report them
        if unmatched_actual or remaining_expected:
            msg_parts = ["Action mismatch (order-independent comparison):"]

            if unmatched_actual:
                msg_parts.append(f"\nUnexpected actions ({len(unmatched_actual)}):")
                for act in unmatched_actual:
                    msg_parts.append(f"  - {act['action']}: {act.get('details', {})}")

            if remaining_expected:
                msg_parts.append(f"\nMissing expected actions ({len(remaining_expected)}):")
                for exp in remaining_expected:
                    msg_parts.append(f"  - {exp['action']}: {exp.get('details', {})}")

            raise AssertionError("\n".join(msg_parts))


# =============================================================================
# MOCK PYGITHUB CLASSES
# =============================================================================


def load_json_data(test_name: str, class_name: str, obj_id: Union[int, str]) -> Dict[str, Any]:
    """
    Load mock data from JSON file.

    Args:
        test_name: Name of the test (subdirectory)
        class_name: PyGithub class name
        obj_id: Object identifier

    Returns:
        Dictionary with object data
    """
    filepath = REPLAY_DATA_DIR / test_name / f"{class_name}_{obj_id}.json"

    if not filepath.exists():
        # Return empty dict if file doesn't exist (allows partial mocking)
        return {}

    with open(filepath) as f:
        return json.load(f)


def save_json_data(
    test_name: str, class_name: str, obj_id: Union[int, str], data: Dict[str, Any]
) -> None:
    """Save mock data to JSON file."""
    dirpath = REPLAY_DATA_DIR / test_name
    dirpath.mkdir(parents=True, exist_ok=True)

    filepath = dirpath / f"{class_name}_{obj_id}.json"

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)


@dataclass
class MockNamedUser:
    """Mock for github.NamedUser.NamedUser"""

    login: str
    id: int = 0
    name: str = ""
    email: str = ""

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "MockNamedUser":
        return cls(
            login=data.get("login", "unknown"),
            id=data.get("id", 0),
            name=data.get("name", ""),
            email=data.get("email", ""),
        )


@dataclass
class MockReaction:
    """Mock for github.Reaction.Reaction"""

    id: int
    content: str
    user: MockNamedUser
    _recorder: ActionRecorder = field(default=None, repr=False)

    def delete(self) -> None:
        """Delete this reaction."""
        if self._recorder:
            self._recorder.record("delete_reaction", reaction_id=self.id, content=self.content)


@dataclass
class MockLabel:
    """Mock for github.Label.Label"""

    name: str
    color: str = "000000"
    description: str = ""

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "MockLabel":
        return cls(
            name=data.get("name", ""),
            color=data.get("color", "000000"),
            description=data.get("description", ""),
        )


@dataclass
class MockCommit:
    """Mock for github.Commit.Commit"""

    sha: str
    message: str = ""
    author: Optional[MockNamedUser] = None
    committer: Optional[MockNamedUser] = None

    # Nested commit data (git commit vs GitHub commit)
    @dataclass
    class GitCommit:
        message: str = ""

        @dataclass
        class GitAuthor:
            date: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
            name: str = ""
            email: str = ""

        author: "MockCommit.GitCommit.GitAuthor" = None
        committer: "MockCommit.GitCommit.GitAuthor" = None

        def __post_init__(self):
            if self.author is None:
                self.author = self.GitAuthor()
            if self.committer is None:
                self.committer = self.GitAuthor()

    commit: GitCommit = None

    def __post_init__(self):
        if self.commit is None:
            self.commit = self.GitCommit(message=self.message)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "MockCommit":
        commit_data = data.get("commit", {})
        author_data = commit_data.get("author", {})
        committer_data = commit_data.get("committer", {})

        git_author = cls.GitCommit.GitAuthor(
            date=parse_timestamp(
                author_data.get("date", datetime.now(tz=timezone.utc).isoformat())
            ),
            name=author_data.get("name", ""),
            email=author_data.get("email", ""),
        )

        git_committer = cls.GitCommit.GitAuthor(
            date=parse_timestamp(
                committer_data.get("date", datetime.now(tz=timezone.utc).isoformat())
            ),
            name=committer_data.get("name", ""),
            email=committer_data.get("email", ""),
        )

        git_commit = cls.GitCommit(
            message=commit_data.get("message", ""),
            author=git_author,
            committer=git_committer,
        )

        return cls(
            sha=data.get("sha", ""),
            message=commit_data.get("message", ""),
            commit=git_commit,
        )


@dataclass
@dataclass
class MockFile:
    """Mock for github.File.File (PR file)"""

    filename: str
    sha: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str = ""
    previous_filename: str = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "MockFile":
        return cls(
            filename=data.get("filename", ""),
            sha=data.get("sha", ""),
            status=data.get("status", "modified"),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changes=data.get("changes", 0),
            patch=data.get("patch", ""),
            previous_filename=data.get("previous_filename"),
        )


@dataclass
class MockIssueComment:
    """Mock for github.IssueComment.IssueComment"""

    id: int
    body: str
    user: MockNamedUser
    created_at: datetime
    updated_at: datetime = None
    _recorder: ActionRecorder = field(default=None, repr=False)
    _reactions: List[MockReaction] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if self.updated_at is None:
            self.updated_at = self.created_at

    def edit(self, body: str) -> None:
        """Edit the comment."""
        if self._recorder:
            self._recorder.record("edit_comment", comment_id=self.id, body=body)
        self.body = body
        self.updated_at = datetime.now(tz=timezone.utc)

    def delete(self) -> None:
        """Delete the comment."""
        if self._recorder:
            self._recorder.record("delete_comment", comment_id=self.id)

    def get_reactions(self) -> "MockPaginatedList":
        """Get reactions on this comment."""
        return MockPaginatedList(self._reactions)

    def create_reaction(self, reaction_type: str) -> MockReaction:
        """Create a reaction on this comment."""
        if self._recorder:
            self._recorder.record(
                "create_reaction",
                comment_id=self.id,
                reaction=reaction_type,
            )

        reaction = MockReaction(
            id=len(self._reactions) + 1,
            content=reaction_type,
            user=MockNamedUser(login="cmsbuild"),
            _recorder=self._recorder,
        )
        self._reactions.append(reaction)
        return reaction

    @classmethod
    def from_json(
        cls, data: Dict[str, Any], recorder: ActionRecorder = None
    ) -> "MockIssueComment":
        user_data = data.get("user", {})
        return cls(
            id=data.get("id", 0),
            body=data.get("body", ""),
            user=MockNamedUser.from_json(user_data),
            created_at=parse_timestamp(
                data.get("created_at", datetime.now(tz=timezone.utc).isoformat())
            ),
            updated_at=(
                parse_timestamp(data.get("updated_at", datetime.now(tz=timezone.utc).isoformat()))
                if data.get("updated_at")
                else None
            ),
            _recorder=recorder,
        )


class MockPaginatedList:
    """Mock for github.PaginatedList.PaginatedList"""

    def __init__(self, items: List[Any]):
        self._items = items

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, index):
        return self._items[index]

    @property
    def reversed(self):
        """Return reversed list (used for getting last commit)."""
        return list(reversed(self._items))


@dataclass
class MockBranch:
    """Mock for branch reference in PR"""

    sha: str
    ref: str = ""
    label: str = ""


class MockPullRequest:
    """Mock for github.PullRequest.PullRequest"""

    def __init__(
        self,
        test_name: str,
        number: int,
        recorder: ActionRecorder = None,
    ):
        self.test_name = test_name
        self.number = number
        self._recorder = recorder

        # Load data from JSON
        data = load_json_data(test_name, "PullRequest", number)

        self.id = data.get("id", number)
        self.title = data.get("title", f"PR #{number}")
        self.body = data.get("body", "")
        self.state = data.get("state", "open")
        self.merged = data.get("merged", False)
        self.mergeable = data.get("mergeable", True)
        self.mergeable_state = data.get("mergeable_state", "clean")

        # Head and base refs
        head_data = data.get("head", {})
        base_data = data.get("base", {})

        self.head = MockBranch(
            sha=head_data.get("sha", "abc123"),
            ref=head_data.get("ref", "feature-branch"),
            label=head_data.get("label", "user:feature-branch"),
        )

        self.base = MockBranch(
            sha=base_data.get("sha", "def456"),
            ref=base_data.get("ref", "main"),
            label=base_data.get("label", "repo:main"),
        )

        # User
        user_data = data.get("user", {"login": "author"})
        self.user = MockNamedUser.from_json(user_data)

        # Load related data - commits_data is a list of commit objects
        self._files = self._load_files(data.get("files", []))
        commits_list = data.get("commits_list", data.get("commits", []))
        self._commits = self._load_commits(commits_list if isinstance(commits_list, list) else [])

        # commits property is an integer count (GitHub API)
        self.commits = data.get("commits_count", len(self._commits))

        # changed_files is an integer count (GitHub API)
        self.changed_files = data.get("changed_files", len(self._files))

    def _load_files(self, files_data: List[Dict]) -> List[MockFile]:
        """Load PR files from data."""
        if files_data:
            return [MockFile.from_json(f) for f in files_data]

        # Try loading from separate file
        files_json = load_json_data(self.test_name, "PullRequestFiles", self.number)
        if files_json and "files" in files_json:
            return [MockFile.from_json(f) for f in files_json["files"]]

        return []

    def _load_commits(self, commits_data: List[Dict]) -> List[MockCommit]:
        """Load PR commits from data."""
        if commits_data:
            return [MockCommit.from_json(c) for c in commits_data]

        # Try loading from separate file
        commits_json = load_json_data(self.test_name, "PullRequestCommits", self.number)
        if commits_json and "commits" in commits_json:
            return [MockCommit.from_json(c) for c in commits_json["commits"]]

        return []

    def get_files(self) -> MockPaginatedList:
        """Get files changed in the PR."""
        return MockPaginatedList(self._files)

    def get_commits(self) -> MockPaginatedList:
        """Get commits in the PR."""
        return MockPaginatedList(self._commits)

    def merge(
        self,
        commit_message: str = None,
        commit_title: str = None,
        merge_method: str = "merge",
        sha: str = None,
    ) -> None:
        """Merge the PR."""
        if self._recorder:
            self._recorder.record(
                "merge_pr",
                pr_number=self.number,
                commit_message=commit_message,
                commit_title=commit_title,
                merge_method=merge_method,
            )
        self.merged = True
        self.state = "closed"

    def create_issue_comment(self, body: str) -> MockIssueComment:
        """Create a comment on the PR."""
        if self._recorder:
            self._recorder.record(
                "create_comment",
                pr_number=self.number,
                body=body,
            )

        return MockIssueComment(
            id=999999,  # Fake ID for new comment
            body=body,
            user=MockNamedUser(login="cmsbuild"),
            created_at=datetime.now(tz=timezone.utc),
            _recorder=self._recorder,
        )


class MockIssue:
    """Mock for github.Issue.Issue"""

    def __init__(
        self,
        test_name: str,
        number: int,
        recorder: ActionRecorder = None,
        is_issue: bool = False,  # If True, this is an issue, not a PR
        comments_data: List[Dict] = None,  # Optional inline comments data
    ):
        self.test_name = test_name
        self.number = number
        self._recorder = recorder
        self._is_issue = is_issue

        # Load data from JSON
        data = load_json_data(test_name, "Issue", number)

        self.id = data.get("id", number)
        self.title = data.get("title", f"Issue #{number}")
        self.body = data.get("body", "")
        self.state = data.get("state", "open")

        # Timestamps
        created_at_str = data.get("created_at", "2024-01-01T00:00:00Z")
        self.created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

        # User
        user_data = data.get("user", {"login": "author"})
        self.user = MockNamedUser.from_json(user_data)

        # Labels
        self._labels = [MockLabel.from_json(l) for l in data.get("labels", [])]

        # Comments - prefer inline data, then JSON file data
        if comments_data is not None:
            self._comments = self._load_comments(comments_data)
        else:
            self._comments = self._load_comments(data.get("comments", []))

        # Associated PR (if this is a PR issue)
        self._pull_request = None if is_issue else "pending"

    def _load_comments(self, comments_data: List[Dict]) -> List[MockIssueComment]:
        """Load issue comments from data."""
        if comments_data:
            return [MockIssueComment.from_json(c, self._recorder) for c in comments_data]

        # Try loading from separate file
        comments_json = load_json_data(self.test_name, "IssueComments", self.number)
        if comments_json and "comments" in comments_json:
            return [
                MockIssueComment.from_json(c, self._recorder) for c in comments_json["comments"]
            ]

        return []

    def get_comments(self) -> MockPaginatedList:
        """Get comments on the issue."""
        return MockPaginatedList(self._comments)

    def get_labels(self) -> MockPaginatedList:
        """Get labels on the issue."""
        return MockPaginatedList(self._labels)

    def add_to_labels(self, *labels: str) -> None:
        """Add labels to the issue."""
        if self._recorder:
            self._recorder.record(
                "add_labels",
                issue_number=self.number,
                labels=list(labels),
            )

        for label_name in labels:
            if not any(l.name == label_name for l in self._labels):
                self._labels.append(MockLabel(name=label_name))

    def remove_from_labels(self, label: str) -> None:
        """Remove a label from the issue."""
        if self._recorder:
            self._recorder.record(
                "remove_label",
                issue_number=self.number,
                label=label,
            )

        self._labels = [l for l in self._labels if l.name != label]

    def create_comment(self, body: str) -> MockIssueComment:
        """Create a comment on the issue."""
        if self._recorder:
            self._recorder.record(
                "create_comment",
                issue_number=self.number,
                body=body,
            )

        comment = MockIssueComment(
            id=len(self._comments) + 1000000,  # Fake ID for new comment
            body=body,
            user=MockNamedUser(login="cmsbuild"),
            created_at=datetime.now(tz=timezone.utc),
            _recorder=self._recorder,
        )
        self._comments.append(comment)
        return comment

    @property
    def pull_request(self):
        """Return pull request marker (used to detect if issue is a PR)."""
        return self._pull_request

    def as_pull_request(self) -> "MockPullRequest":
        """Convert issue to pull request."""
        if self._pull_request is None or self._pull_request == "pending":
            self._pull_request = MockPullRequest(self.test_name, self.number, self._recorder)
        return self._pull_request


class MockRepository:
    """Mock for github.Repository.Repository"""

    def __init__(
        self,
        test_name: str,
        full_name: str = "org/repo",
        recorder: ActionRecorder = None,
    ):
        self.test_name = test_name
        self.full_name = full_name
        self._recorder = recorder

        # Load data from JSON
        data = load_json_data(test_name, "Repository", full_name.replace("/", "_"))

        self.id = data.get("id", 12345)
        self.name = data.get("name", full_name.split("/")[-1])
        self.private = data.get("private", False)
        self.default_branch = data.get("default_branch", "main")

        # Owner is extracted from full_name (org/repo -> org)
        org_name = full_name.split("/")[0]
        owner_data = data.get("owner", {"login": org_name})
        self.owner = MockNamedUser.from_json(owner_data)

    def get_pull(self, number: int) -> MockPullRequest:
        """Get a pull request by number."""
        return MockPullRequest(self.test_name, number, self._recorder)

    def get_issue(self, number: int) -> MockIssue:
        """Get an issue by number."""
        return MockIssue(self.test_name, number, self._recorder)

    def create_status(
        self,
        sha: str,
        state: str,
        target_url: str = None,
        description: str = None,
        context: str = None,
    ) -> None:
        """Create a commit status."""
        if self._recorder:
            self._recorder.record(
                "create_status",
                sha=sha,
                state=state,
                target_url=target_url,
                description=description,
                context=context,
            )


class MockGithub:
    """Mock for github.Github"""

    def __init__(self, test_name: str, recorder: ActionRecorder = None):
        self.test_name = test_name
        self._recorder = recorder

    def get_repo(self, full_name: str) -> MockRepository:
        """Get a repository by name."""
        return MockRepository(self.test_name, full_name, self._recorder)


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def test_name(request):
    """Get the current test name."""
    return request.node.name


@pytest.fixture
def action_recorder(test_name, record_mode):
    """Create an action recorder for the test."""
    return ActionRecorder(test_name, record_mode)


@pytest.fixture
def mock_gh(test_name, action_recorder):
    """Create a mock GitHub instance."""
    return MockGithub(test_name, action_recorder)


@pytest.fixture
def mock_repo(test_name, action_recorder):
    """Create a mock repository."""
    return MockRepository(test_name, recorder=action_recorder)


@pytest.fixture
def mock_issue(test_name, action_recorder):
    """Create a mock issue."""
    return MockIssue(test_name, number=1, recorder=action_recorder)


@pytest.fixture
def repo_config():
    """Get default repository configuration as a mock module."""
    return create_mock_repo_config()


# =============================================================================
# HELPER FUNCTIONS FOR TEST DATA CREATION
# =============================================================================


def create_test_data_directory(test_name: str) -> Path:
    """Create directory for test replay data."""
    dirpath = REPLAY_DATA_DIR / test_name
    dirpath.mkdir(parents=True, exist_ok=True)
    return dirpath


def create_basic_pr_data(
    test_name: str,
    pr_number: int = 1,
    files: List[Dict] = None,
    comments: List[Dict] = None,
    commits: List[Dict] = None,
    labels: List[str] = None,
) -> None:
    """
    Create basic test data files for a PR.

    This is a helper for setting up test fixtures.
    """
    dirpath = create_test_data_directory(test_name)

    # Default file
    if files is None:
        files = [
            {
                "filename": "src/core/main.py",
                "sha": "abc123def456",
                "status": "modified",
            }
        ]

    # Default commit
    if commits is None:
        commits = [
            {
                "sha": "commit123",
                "commit": {
                    "message": "Test commit",
                    "author": {
                        "date": datetime.now(tz=timezone.utc).isoformat(),
                        "name": "Test Author",
                        "email": "test@example.com",
                    },
                    "committer": {
                        "date": datetime.now(tz=timezone.utc).isoformat(),
                        "name": "Test Committer",
                        "email": "test@example.com",
                    },
                },
            }
        ]

    # Default comments (empty)
    if comments is None:
        comments = []

    # Default labels (empty)
    if labels is None:
        labels = []

    # Create PR data
    pr_data = {
        "id": pr_number,
        "number": pr_number,
        "title": f"Test PR #{pr_number}",
        "body": "Test PR body",
        "state": "open",
        "merged": False,
        "mergeable": True,
        "head": {"sha": commits[-1]["sha"] if commits else "abc123", "ref": "feature"},
        "base": {"sha": "base123", "ref": "main"},
        "user": {"login": "testuser", "id": 1},
        "files": files,
        "commits": commits,
    }

    save_json_data(test_name, "PullRequest", pr_number, pr_data)

    # Create Issue data (for the PR)
    issue_data = {
        "id": pr_number,
        "number": pr_number,
        "title": f"Test PR #{pr_number}",
        "body": "Test PR body",
        "state": "open",
        "user": {"login": "testuser", "id": 1},
        "labels": [{"name": l} for l in labels],
        "comments": comments,
    }

    save_json_data(test_name, "Issue", pr_number, issue_data)

    # Create Repository data
    repo_data = {
        "id": 12345,
        "name": "repo",
        "full_name": "org/repo",
        "private": False,
        "default_branch": "main",
    }

    save_json_data(test_name, "Repository", "org_repo", repo_data)


# =============================================================================
# TESTS
# =============================================================================


class TestBasicFunctionality:
    """Tests for basic PR processing functionality."""

    def test_new_pr_initialization(
        self, mock_gh, mock_repo, mock_issue, repo_config, action_recorder, record_mode
    ):
        """Test that a new PR is properly initialized with pending status."""
        # Setup: Create test data for a new PR with no comments
        create_basic_pr_data(
            "test_new_pr_initialization",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[],
        )

        # Recreate mocks with proper test name
        recorder = ActionRecorder("test_new_pr_initialization", record_mode)
        gh = MockGithub("test_new_pr_initialization", recorder)
        repo = MockRepository("test_new_pr_initialization", recorder=recorder)
        issue = MockIssue("test_new_pr_initialization", number=1, recorder=recorder)

        # Execute
        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Verify result structure
        assert result["pr_number"] == 1
        assert result["pr_state"] in ["tests-pending", "signatures-pending"]
        assert "categories" in result

        # Handle recording/comparison
        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_basic_approval(self, repo_config, record_mode):
        """Test that +1 approval from L2 member works correctly."""
        # Setup: Create PR with an approval comment
        create_basic_pr_data(
            "test_basic_approval",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},  # alice is in 'core' team
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        # Create mocks
        recorder = ActionRecorder("test_basic_approval", record_mode)
        gh = MockGithub("test_basic_approval", recorder)
        repo = MockRepository("test_basic_approval", recorder=recorder)
        issue = MockIssue("test_basic_approval", number=1, recorder=recorder)

        # Execute
        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Verify
        assert result["pr_number"] == 1

        # Handle recording/comparison
        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_category_specific_approval(self, repo_config, record_mode):
        """Test approval for a specific category (+core)."""
        create_basic_pr_data(
            "test_category_specific_approval",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+core",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_category_specific_approval", record_mode)
        gh = MockGithub("test_category_specific_approval", recorder)
        repo = MockRepository("test_category_specific_approval", recorder=recorder)
        issue = MockIssue("test_category_specific_approval", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_rejection(self, repo_config, record_mode):
        """Test that -1 rejection works correctly."""
        create_basic_pr_data(
            "test_rejection",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "-1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_rejection", record_mode)
        gh = MockGithub("test_rejection", recorder)
        repo = MockRepository("test_rejection", recorder=recorder)
        issue = MockIssue("test_rejection", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestHoldMechanism:
    """Tests for the hold/unhold mechanism."""

    def test_hold_command(self, repo_config, record_mode):
        """Test that hold command prevents merge."""
        create_basic_pr_data(
            "test_hold_command",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "hold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_hold_command", record_mode)
        gh = MockGithub("test_hold_command", recorder)
        repo = MockRepository("test_hold_command", recorder=recorder)
        issue = MockIssue("test_hold_command", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert len(result["holds"]) > 0
        assert result["can_merge"] is False

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_unhold_same_category(self, repo_config, record_mode):
        """Test that L2 member can unhold their own category."""
        create_basic_pr_data(
            "test_unhold_same_category",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "hold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "unhold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_unhold_same_category", record_mode)
        gh = MockGithub("test_unhold_same_category", recorder)
        repo = MockRepository("test_unhold_same_category", recorder=recorder)
        issue = MockIssue("test_unhold_same_category", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert len(result["holds"]) == 0

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_orp_unhold_all(self, repo_config, record_mode):
        """Test that ORP can unhold all holds."""
        create_basic_pr_data(
            "test_orp_unhold_all",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "hold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "hold",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 102,
                    "body": "unhold",
                    "user": {"login": "dave", "id": 4},  # dave is ORP
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_orp_unhold_all", record_mode)
        gh = MockGithub("test_orp_unhold_all", recorder)
        repo = MockRepository("test_orp_unhold_all", recorder=recorder)
        issue = MockIssue("test_orp_unhold_all", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert len(result["holds"]) == 0

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestAssignCommand:
    """Tests for the assign command."""

    def test_assign_category(self, repo_config, record_mode):
        """Test assigning a new category."""
        create_basic_pr_data(
            "test_assign_category",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign visualization",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_assign_category", record_mode)
        gh = MockGithub("test_assign_category", recorder)
        repo = MockRepository("test_assign_category", recorder=recorder)
        issue = MockIssue("test_assign_category", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert "visualization" in result["categories"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_assign_from_package(self, repo_config, record_mode):
        """Test assigning category from package mapping."""
        create_basic_pr_data(
            "test_assign_from_package",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign from numpy",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_assign_from_package", record_mode)
        gh = MockGithub("test_assign_from_package", recorder)
        repo = MockRepository("test_assign_from_package", recorder=recorder)
        issue = MockIssue("test_assign_from_package", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # numpy maps to 'analysis' category
        assert "analysis" in result["categories"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestCommandPreprocessing:
    """Tests for command preprocessing and parsing."""

    def test_cmsbuild_prefix_removal(self, repo_config, record_mode):
        """Test that @cmsbuild prefix is properly removed."""
        create_basic_pr_data(
            "test_cmsbuild_prefix_removal",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "@cmsbuild please +1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_cmsbuild_prefix_removal", record_mode)
        gh = MockGithub("test_cmsbuild_prefix_removal", recorder)
        repo = MockRepository("test_cmsbuild_prefix_removal", recorder=recorder)
        issue = MockIssue("test_cmsbuild_prefix_removal", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_please_prefix_removal(self, repo_config, record_mode):
        """Test that 'please' prefix is properly removed."""
        # Create PR with code-checks approval (required for tests)
        create_basic_pr_data(
            "test_please_prefix_removal",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+code-checks",
                    "user": {"login": "cmsbuild", "id": 10},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "please test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_please_prefix_removal", record_mode)
        gh = MockGithub("test_please_prefix_removal", recorder)
        repo = MockRepository("test_please_prefix_removal", recorder=recorder)
        issue = MockIssue("test_please_prefix_removal", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Check that a test was triggered (please prefix was removed)
        assert len(result["tests_triggered"]) > 0
        assert result["tests_triggered"][0]["verb"] == "test"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestMultipleFiles:
    """Tests for PRs with multiple files."""

    def test_multiple_files_multiple_categories(self, repo_config, record_mode):
        """Test PR touching files in multiple L2 categories."""
        create_basic_pr_data(
            "test_multiple_files_multiple_categories",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_1",
                    "status": "modified",
                },
                {
                    "filename": "src/analysis/analyzer.py",
                    "sha": "file_sha_2",
                    "status": "modified",
                },
                {
                    "filename": "docs/README.md",
                    "sha": "file_sha_3",
                    "status": "modified",
                },
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},  # alice: core, analysis
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_multiple_files_multiple_categories", record_mode)
        gh = MockGithub("test_multiple_files_multiple_categories", recorder)
        repo = MockRepository("test_multiple_files_multiple_categories", recorder=recorder)
        issue = MockIssue("test_multiple_files_multiple_categories", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Should have multiple categories
        categories = result["categories"]
        assert len(categories) >= 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestTestCommand:
    """Tests for the test trigger command."""

    def test_basic_test_trigger(self, repo_config, record_mode):
        """Test basic test trigger command."""
        # Create PR with code-checks approval (required for tests)
        create_basic_pr_data(
            "test_basic_test_trigger",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+code-checks",
                    "user": {"login": "cmsbuild", "id": 10},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_basic_test_trigger", record_mode)
        gh = MockGithub("test_basic_test_trigger", recorder)
        repo = MockRepository("test_basic_test_trigger", recorder=recorder)
        issue = MockIssue("test_basic_test_trigger", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Check that a test was triggered
        assert len(result["tests_triggered"]) > 0
        assert result["tests_triggered"][0]["verb"] == "test"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_with_params(self, repo_config, record_mode):
        """Test trigger with parameters."""
        # Create PR with code-checks approval (required for tests)
        create_basic_pr_data(
            "test_test_with_params",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+code-checks",
                    "user": {"login": "cmsbuild", "id": 10},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "test workflows 1.0,2.0",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_test_with_params", record_mode)
        gh = MockGithub("test_test_with_params", recorder)
        repo = MockRepository("test_test_with_params", recorder=recorder)
        issue = MockIssue("test_test_with_params", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # Check that a test was triggered with workflows
        assert len(result["tests_triggered"]) > 0
        assert result["tests_triggered"][0]["verb"] == "test"
        assert "1.0" in result["tests_triggered"][0]["workflows"]
        assert "2.0" in result["tests_triggered"][0]["workflows"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestCacheManagement:
    """Tests for cache storage and retrieval."""

    def test_cache_creation(self, repo_config, record_mode):
        """Test that cache is created in comments."""
        create_basic_pr_data(
            "test_cache_creation",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[],
        )

        recorder = ActionRecorder("test_cache_creation", record_mode)
        gh = MockGithub("test_cache_creation", recorder)
        repo = MockRepository("test_cache_creation", recorder=recorder)
        issue = MockIssue("test_cache_creation", number=1, recorder=recorder)

        # Run with dryRun=False to actually create cache (but still mock)
        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,  # Still dry run to not actually post
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestMergeCommand:
    """Tests for the merge command."""

    def test_merge_when_ready(self, repo_config, record_mode):
        """Test merge command when PR is ready."""
        # Disable all checks for this test
        config = create_mock_repo_config(
            PRE_CHECKS=[],  # No pre-checks required
            EXTRA_CHECKS=[],  # No extra checks required (including ORP)
        )

        create_basic_pr_data(
            "test_merge_when_ready",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "merge",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_merge_when_ready", record_mode)
        gh = MockGithub("test_merge_when_ready", recorder)
        repo = MockRepository("test_merge_when_ready", recorder=recorder)
        issue = MockIssue("test_merge_when_ready", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestBranchRewrite:
    """Tests for handling branch rewrites (rebases, force-pushes)."""

    def test_signature_invalidation_on_file_change(self, repo_config, record_mode):
        """Test that signatures are invalidated when files change."""
        # First create initial PR state with approval
        create_basic_pr_data(
            "test_signature_invalidation_on_file_change",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "new_file_sha_456",  # Different SHA simulates file change
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_signature_invalidation_on_file_change", record_mode)
        gh = MockGithub("test_signature_invalidation_on_file_change", recorder)
        repo = MockRepository("test_signature_invalidation_on_file_change", recorder=recorder)
        issue = MockIssue(
            "test_signature_invalidation_on_file_change", number=1, recorder=recorder
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_comment(self, repo_config, record_mode):
        """Test handling of empty comments."""
        create_basic_pr_data(
            "test_empty_comment",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_empty_comment", record_mode)
        gh = MockGithub("test_empty_comment", recorder)
        repo = MockRepository("test_empty_comment", recorder=recorder)
        issue = MockIssue("test_empty_comment", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_non_command_comment(self, repo_config, record_mode):
        """Test that non-command comments are ignored."""
        create_basic_pr_data(
            "test_non_command_comment",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "This is just a regular comment, not a command.",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_non_command_comment", record_mode)
        gh = MockGithub("test_non_command_comment", recorder)
        repo = MockRepository("test_non_command_comment", recorder=recorder)
        issue = MockIssue("test_non_command_comment", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # No tests should be triggered, no approvals processed
        assert result["pr_number"] == 1
        assert len(result["tests_triggered"]) == 0

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_comment_ignored(self, repo_config, record_mode):
        """Test that bot's own comments are ignored."""
        create_basic_pr_data(
            "test_bot_comment_ignored",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_comment_ignored", record_mode)
        gh = MockGithub("test_bot_comment_ignored", recorder)
        repo = MockRepository("test_bot_comment_ignored", recorder=recorder)
        issue = MockIssue("test_bot_comment_ignored", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_user_not_in_l2(self, repo_config, record_mode):
        """Test approval from user not in any L2 team."""
        create_basic_pr_data(
            "test_user_not_in_l2",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "unknown_user", "id": 999},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_user_not_in_l2", record_mode)
        gh = MockGithub("test_user_not_in_l2", recorder)
        repo = MockRepository("test_user_not_in_l2", recorder=recorder)
        issue = MockIssue("test_user_not_in_l2", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # User not in L2, so no approval should be recorded
        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestBotMessageProcessing:
    """Tests for processing bot's own messages (CI results, code-checks, etc.)."""

    def test_bot_code_checks_pass(self, repo_config, record_mode):
        """Test that +code-checks from bot is processed."""
        create_basic_pr_data(
            "test_bot_code_checks_pass",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+code-checks",
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_code_checks_pass", record_mode)
        gh = MockGithub("test_bot_code_checks_pass", recorder)
        repo = MockRepository("test_bot_code_checks_pass", recorder=recorder)
        issue = MockIssue("test_bot_code_checks_pass", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # The code-checks command should have been processed

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_code_checks_fail(self, repo_config, record_mode):
        """Test that -code-checks from bot is processed."""
        create_basic_pr_data(
            "test_bot_code_checks_fail",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "-code-checks",
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_code_checks_fail", record_mode)
        gh = MockGithub("test_bot_code_checks_fail", recorder)
        repo = MockRepository("test_bot_code_checks_fail", recorder=recorder)
        issue = MockIssue("test_bot_code_checks_fail", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_ci_approval(self, repo_config, record_mode):
        """Test that +1 from bot (CI results) is processed when bot has L2 categories."""
        # L2 data is already set up by fixture with cmsbuild having tests/code-checks

        create_basic_pr_data(
            "test_bot_ci_approval",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_ci_approval", record_mode)
        gh = MockGithub("test_bot_ci_approval", recorder)
        repo = MockRepository("test_bot_ci_approval", recorder=recorder)
        issue = MockIssue("test_bot_ci_approval", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # The +1 should be processed for bot's L2 categories (tests, code-checks)

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_category_specific_approval(self, repo_config, record_mode):
        """Test that +tests from bot is processed."""
        # L2 data is already set up by fixture with cmsbuild having tests/code-checks

        create_basic_pr_data(
            "test_bot_category_specific_approval",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+tests",
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_category_specific_approval", record_mode)
        gh = MockGithub("test_bot_category_specific_approval", recorder)
        repo = MockRepository("test_bot_category_specific_approval", recorder=recorder)
        issue = MockIssue("test_bot_category_specific_approval", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_regular_comment_still_ignored(self, repo_config, record_mode):
        """Test that non-allowed bot comments are still ignored."""
        create_basic_pr_data(
            "test_bot_regular_comment_still_ignored",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "hold",  # hold is NOT in bot-allowed commands
                    "user": {"login": "cmsbuild", "id": 999},  # Bot's own comment
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_regular_comment_still_ignored", record_mode)
        gh = MockGithub("test_bot_regular_comment_still_ignored", recorder)
        repo = MockRepository("test_bot_regular_comment_still_ignored", recorder=recorder)
        issue = MockIssue("test_bot_regular_comment_still_ignored", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # hold command from bot should NOT be processed
        assert result["pr_number"] == 1
        assert len(result["holds"]) == 0

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestBuildTestCommandParsing:
    """Tests for build/test command parsing."""

    def test_parse_simple_test(self):
        """Test parsing simple 'test' command."""
        result = parse_test_cmd("test")
        assert result.verb == "test"
        assert result.workflows == []
        assert result.prs == []
        assert result.queue == ""

    def test_parse_simple_build(self):
        """Test parsing simple 'build' command."""
        result = parse_test_cmd("build")
        assert result.verb == "build"

    def test_parse_test_with_workflows(self):
        """Test parsing 'test workflows 1.0,2.0,3.0'."""
        result = parse_test_cmd("test workflows 1.0,2.0,3.0")
        assert result.verb == "test"
        assert result.workflows == ["1.0", "2.0", "3.0"]

    def test_parse_test_with_workflow_singular(self):
        """Test parsing 'test workflow 1.0'."""
        result = parse_test_cmd("test workflow 1.0")
        assert result.verb == "test"
        assert result.workflows == ["1.0"]

    def test_parse_test_with_prs(self):
        """Test parsing 'test with cms-sw/cmssw#12345,#67890'."""
        result = parse_test_cmd("test with cms-sw/cmssw#12345,#67890")
        assert result.verb == "test"
        assert result.prs == ["cms-sw/cmssw#12345", "#67890"]

    def test_parse_test_with_queue(self):
        """Test parsing 'test for el8_amd64_gcc12'."""
        result = parse_test_cmd("test for el8_amd64_gcc12")
        assert result.verb == "test"
        assert result.queue == "el8_amd64_gcc12"

    def test_parse_build_using_full_cmssw(self):
        """Test parsing 'build using full cmssw'."""
        result = parse_test_cmd("build using full cmssw")
        assert result.verb == "build"
        assert result.using is True
        assert result.full == "cmssw"

    def test_parse_test_using_addpkg(self):
        """Test parsing 'test using addpkg RecoTracker/PixelSeeding'."""
        result = parse_test_cmd("test using addpkg RecoTracker/PixelSeeding")
        assert result.verb == "test"
        assert result.using is True
        assert result.addpkg == ["RecoTracker/PixelSeeding"]

    def test_parse_test_using_cms_addpkg(self):
        """Test parsing 'test using cms-addpkg Pkg1,Pkg2'."""
        result = parse_test_cmd("test using cms-addpkg Pkg1,Pkg2")
        assert result.verb == "test"
        assert result.addpkg == ["Pkg1", "Pkg2"]

    def test_parse_complex_command(self):
        """Test parsing complex command with multiple options."""
        result = parse_test_cmd(
            "build workflows 1.0,2.0 with #123 for el8_amd64_gcc12 using full cmssw"
        )
        assert result.verb == "build"
        assert result.workflows == ["1.0", "2.0"]
        assert result.prs == ["#123"]
        assert result.queue == "el8_amd64_gcc12"
        assert result.full == "cmssw"

    def test_parse_error_empty(self):
        """Test that empty input raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("")

    def test_parse_error_unknown_verb(self):
        """Test that unknown verb raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("deploy")

    def test_parse_error_duplicate_keyword(self):
        """Test that duplicate keyword raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("test workflows 1.0 workflows 2.0")

    def test_parse_error_missing_parameter(self):
        """Test that missing parameter raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("test workflows")

    def test_parse_error_empty_using(self):
        """Test that empty using statement raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("test using")

    def test_parse_error_full_without_using(self):
        """Test that 'full' without 'using' raises error."""
        with pytest.raises(TestCmdParseError):
            parse_test_cmd("test full cmssw")


class TestBuildTestCommand:
    """Tests for build/test command execution."""

    def test_build_command_basic(self, repo_config, record_mode):
        """Test basic build command."""
        # Remove pre-checks for this test
        config = create_mock_repo_config(PRE_CHECKS=[])

        create_basic_pr_data(
            "test_build_command_basic",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "build",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_build_command_basic", record_mode)
        gh = MockGithub("test_build_command_basic", recorder)
        repo = MockRepository("test_build_command_basic", recorder=recorder)
        issue = MockIssue("test_build_command_basic", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert len(result["tests_triggered"]) == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_command_with_workflows(self, repo_config, record_mode):
        """Test test command with workflows parameter."""
        config = create_mock_repo_config(PRE_CHECKS=[])

        create_basic_pr_data(
            "test_test_command_with_workflows",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test workflows 1.0,2.0,3.0",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_test_command_with_workflows", record_mode)
        gh = MockGithub("test_test_command_with_workflows", recorder)
        repo = MockRepository("test_test_command_with_workflows", recorder=recorder)
        issue = MockIssue("test_test_command_with_workflows", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert len(result["tests_triggered"]) == 1
        # Check that the test request has workflows
        test_req = result["tests_triggered"][0]
        assert "1.0" in test_req["workflows"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_blocked_by_missing_signature(self, repo_config, record_mode):
        """Test that test is blocked when required signature is missing."""
        config = create_mock_repo_config(PRE_CHECKS=[(0, ["code-checks"])])

        create_basic_pr_data(
            "test_test_blocked_by_missing_signature",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_test_blocked_by_missing_signature", record_mode)
        gh = MockGithub("test_test_blocked_by_missing_signature", recorder)
        repo = MockRepository("test_test_blocked_by_missing_signature", recorder=recorder)
        issue = MockIssue("test_test_blocked_by_missing_signature", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Test should NOT be triggered because code-checks is not approved
        assert len(result["tests_triggered"]) == 0
        # Should have a message about missing signature
        assert any("code-checks" in msg for msg in result["messages"])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestPRDescriptionParsing:
    """Tests for PR/Issue ignore logic and notification tags."""

    def _make_mock_issue(self, number=1, title="Test Issue", body=""):
        """Create a mock issue for testing."""
        issue = MagicMock()
        issue.number = number
        issue.title = title
        issue.body = body
        return issue

    def _make_mock_repo(self, full_name="cms-sw/cmssw"):
        """Create a mock repo for testing."""
        repo = MagicMock()
        repo.full_name = full_name
        return repo

    def test_should_ignore_issue_with_cms_bot_tag(self):
        """Test that <cms-bot></cms-bot> tag in body is detected."""
        repo_config = create_mock_repo_config()
        repo = self._make_mock_repo()

        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="<cms-bot></cms-bot>")
            )
            is True
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="<cms-bot> </cms-bot>")
            )
            is True
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="<CMS-BOT></CMS-BOT>")
            )
            is True
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="  <cms-bot></cms-bot>  ")
            )
            is True
        )

    def test_should_not_ignore_issue_without_tag(self):
        """Test that issues without the tag are not ignored."""
        repo_config = create_mock_repo_config()
        repo = self._make_mock_repo()

        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(body="")) is False
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="Normal PR description")
            )
            is False
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="Fix bug in module\n\nDetails here")
            )
            is False
        )

    def test_should_not_ignore_issue_with_tag_not_on_first_line(self):
        """Test that tag must be on first non-blank line."""
        repo_config = create_mock_repo_config()
        repo = self._make_mock_repo()

        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="Some text\n<cms-bot></cms-bot>")
            )
            is False
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(body="\n\nSome text\n<cms-bot></cms-bot>")
            )
            is False
        )

    def test_should_ignore_issue_in_ignore_list(self):
        """Test that issues in IGNORE_ISSUES are ignored."""
        repo_config = create_mock_repo_config(IGNORE_ISSUES={42: True})
        repo = self._make_mock_repo()

        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(number=42)) is True
        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(number=43)) is False

    def test_should_ignore_issue_in_repo_specific_ignore_list(self):
        """Test that issues in repo-specific IGNORE_ISSUES are ignored."""
        repo_config = create_mock_repo_config(
            IGNORE_ISSUES={"cms-sw/cmssw": {100: True, 101: True}}
        )
        repo = self._make_mock_repo(full_name="cms-sw/cmssw")
        other_repo = self._make_mock_repo(full_name="cms-sw/cmsdist")

        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(number=100)) is True
        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(number=101)) is True
        assert should_ignore_issue(repo_config, repo, self._make_mock_issue(number=102)) is False
        # Same issue number in different repo should not be ignored
        assert (
            should_ignore_issue(repo_config, other_repo, self._make_mock_issue(number=100))
            is False
        )

    def test_should_ignore_issue_with_build_rel_title(self):
        """Test that issues with BUILD_REL pattern in title are ignored."""
        repo_config = create_mock_repo_config()
        repo = self._make_mock_repo()

        # BUILD_REL pattern: ^[Bb]uild[ ]+(CMSSW_[^ ]+)
        # Matches titles like "Build CMSSW_14_0_0" or "build CMSSW_14_0_0_pre1"
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(title="Build CMSSW_14_0_0")
            )
            is True
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(title="build CMSSW_14_0_0_pre1")
            )
            is True
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(title="Build CMSSW_12_0_X")
            )
            is True
        )

        # Normal titles should not be ignored
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(title="Normal issue title")
            )
            is False
        )
        assert (
            should_ignore_issue(repo_config, repo, self._make_mock_issue(title="Fix bug in Build"))
            is False
        )
        assert (
            should_ignore_issue(
                repo_config, repo, self._make_mock_issue(title="Release CMSSW_14_0_0")
            )
            is False
        )  # "Release" not "Build"

    def test_should_notify_without_at(self):
        """Test that <notify></notify> tag is detected."""
        assert should_notify_without_at("<notify></notify>") is True
        assert should_notify_without_at("<notify> </notify>") is True
        assert should_notify_without_at("<NOTIFY></NOTIFY>") is True
        assert should_notify_without_at("  <notify></notify>  ") is True

    def test_should_notify_with_at(self):
        """Test that PRs without notify tag use @ in mentions."""
        assert should_notify_without_at("") is False
        assert should_notify_without_at("Normal PR description") is False
        assert should_notify_without_at("<notify>content</notify>") is False


class TestPRIgnoreProcessing:
    """Tests for PR ignore functionality via <cms-bot> tag."""

    def test_pr_with_cms_bot_tag_skipped(self, repo_config, record_mode):
        """Test that PR with <cms-bot></cms-bot> is skipped."""
        create_basic_pr_data(
            "test_pr_with_cms_bot_tag_skipped",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        # Modify PR data to have cms-bot tag in body
        pr_data_path = REPLAY_DATA_DIR / "test_pr_with_cms_bot_tag_skipped" / "PullRequest_1.json"
        with open(pr_data_path, "r") as f:
            pr_data = json.load(f)
        pr_data["body"] = "<cms-bot></cms-bot>\nThis PR should be ignored"
        with open(pr_data_path, "w") as f:
            json.dump(pr_data, f, indent=2)

        recorder = ActionRecorder("test_pr_with_cms_bot_tag_skipped", record_mode)
        gh = MockGithub("test_pr_with_cms_bot_tag_skipped", recorder)
        repo = MockRepository("test_pr_with_cms_bot_tag_skipped", recorder=recorder)
        issue = MockIssue("test_pr_with_cms_bot_tag_skipped", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["skipped"] is True
        assert result["reason"] == "cms-bot ignore tag"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_pr_with_cms_bot_tag_processed_with_force(self, repo_config, record_mode):
        """Test that PR with <cms-bot></cms-bot> is processed when force=True."""
        create_basic_pr_data(
            "test_pr_with_cms_bot_tag_processed_with_force",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[],
        )

        # Modify PR data to have cms-bot tag in body
        pr_data_path = (
            REPLAY_DATA_DIR
            / "test_pr_with_cms_bot_tag_processed_with_force"
            / "PullRequest_1.json"
        )
        with open(pr_data_path, "r") as f:
            pr_data = json.load(f)
        pr_data["body"] = "<cms-bot></cms-bot>\nThis PR should be ignored"
        with open(pr_data_path, "w") as f:
            json.dump(pr_data, f, indent=2)

        recorder = ActionRecorder("test_pr_with_cms_bot_tag_processed_with_force", record_mode)
        gh = MockGithub("test_pr_with_cms_bot_tag_processed_with_force", recorder)
        repo = MockRepository("test_pr_with_cms_bot_tag_processed_with_force", recorder=recorder)
        issue = MockIssue(
            "test_pr_with_cms_bot_tag_processed_with_force", number=1, recorder=recorder
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            force=True,  # Force processing
            loglevel="WARNING",
        )

        # Should NOT be skipped because force=True
        assert result.get("skipped") is not True
        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# NEW TESTS FOR RECENT FEATURES
# =============================================================================


class TestSignatureLocking:
    """Tests for signature locking after commits."""

    def test_signature_locked_after_commit(self, repo_config, record_mode):
        """Test that signatures are locked after a commit is pushed."""
        # Create PR with approval, then a commit after
        create_basic_pr_data(
            "test_signature_locked_after_commit",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": "2024-01-01T10:00:00Z",  # Comment at 10:00
                }
            ],
            commits=[
                {
                    "sha": "commit_sha_1",
                    "author": {"login": "author1", "date": "2024-01-01T09:00:00Z"},
                    "committer": {"date": "2024-01-01T09:00:00Z"},
                    "message": "Initial commit",
                },
                {
                    "sha": "commit_sha_2",
                    "author": {
                        "login": "author1",
                        "date": "2024-01-01T11:00:00Z",
                    },  # After comment
                    "committer": {"date": "2024-01-01T11:00:00Z"},
                    "message": "Second commit",
                },
            ],
        )

        recorder = ActionRecorder("test_signature_locked_after_commit", record_mode)
        gh = MockGithub("test_signature_locked_after_commit", recorder)
        repo = MockRepository("test_signature_locked_after_commit", recorder=recorder)
        issue = MockIssue("test_signature_locked_after_commit", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # The signature should be locked because commit happened after

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_signature_not_locked_before_commit(self, repo_config, record_mode):
        """Test that signatures are not locked if no commit after."""
        create_basic_pr_data(
            "test_signature_not_locked_before_commit",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+1",
                    "user": {"login": "alice", "id": 2},
                    "created_at": "2024-01-01T12:00:00Z",  # Comment at 12:00
                }
            ],
            commits=[
                {
                    "sha": "commit_sha_1",
                    "author": {
                        "login": "author1",
                        "date": "2024-01-01T10:00:00Z",
                    },  # Before comment
                    "committer": {"date": "2024-01-01T10:00:00Z"},
                    "message": "Initial commit",
                }
            ],
        )

        recorder = ActionRecorder("test_signature_not_locked_before_commit", record_mode)
        gh = MockGithub("test_signature_not_locked_before_commit", recorder)
        repo = MockRepository("test_signature_not_locked_before_commit", recorder=recorder)
        issue = MockIssue("test_signature_not_locked_before_commit", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestUnassignCommand:
    """Tests for unassign command."""

    def test_unassign_category(self, repo_config, record_mode):
        """Test unassign command removes category."""
        create_basic_pr_data(
            "test_unassign_category",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign core",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "unassign core",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_unassign_category", record_mode)
        gh = MockGithub("test_unassign_category", recorder)
        repo = MockRepository("test_unassign_category", recorder=recorder)
        issue = MockIssue("test_unassign_category", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_unassign_invalid_category(self, repo_config, record_mode):
        """Test unassign with invalid category fails gracefully."""
        create_basic_pr_data(
            "test_unassign_invalid_category",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "unassign nonexistent-category",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_unassign_invalid_category", record_mode)
        gh = MockGithub("test_unassign_invalid_category", recorder)
        repo = MockRepository("test_unassign_invalid_category", recorder=recorder)
        issue = MockIssue("test_unassign_invalid_category", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Should have error message about unknown category
        assert any("nonexistent-category" in msg for msg in result["messages"])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestCommaSeparatedAssign:
    """Tests for comma-separated assign/unassign commands."""

    def test_assign_multiple_categories(self, repo_config, record_mode):
        """Test assigning multiple categories at once."""
        create_basic_pr_data(
            "test_assign_multiple_categories",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign core,analysis,simulation",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_assign_multiple_categories", record_mode)
        gh = MockGithub("test_assign_multiple_categories", recorder)
        repo = MockRepository("test_assign_multiple_categories", recorder=recorder)
        issue = MockIssue("test_assign_multiple_categories", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_unassign_multiple_categories(self, repo_config, record_mode):
        """Test unassigning multiple categories at once."""
        create_basic_pr_data(
            "test_unassign_multiple_categories",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign core,analysis",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "unassign core,analysis",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_unassign_multiple_categories", record_mode)
        gh = MockGithub("test_unassign_multiple_categories", recorder)
        repo = MockRepository("test_unassign_multiple_categories", recorder=recorder)
        issue = MockIssue("test_unassign_multiple_categories", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_assign_mixed_valid_invalid(self, repo_config, record_mode):
        """Test assign with mix of valid and invalid categories."""
        create_basic_pr_data(
            "test_assign_mixed_valid_invalid",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign core,invalid_cat,analysis",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_assign_mixed_valid_invalid", record_mode)
        gh = MockGithub("test_assign_mixed_valid_invalid", recorder)
        repo = MockRepository("test_assign_mixed_valid_invalid", recorder=recorder)
        issue = MockIssue("test_assign_mixed_valid_invalid", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Should have error message about invalid category
        assert any("invalid_cat" in msg for msg in result["messages"])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestIssueProcessing:
    """Tests for Issue (non-PR) processing."""

    def test_issue_skips_pr_only_commands(self, repo_config, record_mode):
        """Test that PR-only commands are ignored for issues."""
        create_basic_pr_data(
            "test_issue_skips_pr_only_commands",
            pr_number=1,
            files=[],  # Issues don't have files
            comments=[
                {
                    "id": 100,
                    "body": "+1",  # This is a PR-only command
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_issue_skips_pr_only_commands", record_mode)
        gh = MockGithub("test_issue_skips_pr_only_commands", recorder)
        repo = MockRepository("test_issue_skips_pr_only_commands", recorder=recorder)
        issue = MockIssue(
            "test_issue_skips_pr_only_commands", number=1, recorder=recorder, is_issue=True
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert result["is_pr"] is False

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


class TestExtractCommandLine:
    """Tests for extract_command_line function."""

    def test_extract_simple(self):
        """Test extracting simple commands."""
        assert extract_command_line("+1") == "+1"
        assert extract_command_line("  +1  ") == "+1"
        assert extract_command_line("+1\nsome text") == "+1"

    def test_extract_with_prefix(self):
        """Test extracting commands with @cmsbuild prefix."""
        assert extract_command_line("@cmsbuild +1") == "+1"
        assert extract_command_line("@cmsbuild please +1") == "+1"
        assert extract_command_line("please +1") == "+1"

    def test_extract_empty(self):
        """Test extracting from empty/whitespace content."""
        assert extract_command_line("") is None
        assert extract_command_line("   ") is None
        assert extract_command_line("\n\n\n") is None

    def test_extract_preserves_command(self):
        """Test that command content is preserved."""
        assert extract_command_line("test workflows 1.0,2.0") == "test workflows 1.0,2.0"
        assert extract_command_line("assign core,analysis") == "assign core,analysis"


class TestHyphenatedCategories:
    """Tests for hyphenated category names like code-checks."""

    def test_plus_category_with_hyphen(self, repo_config, record_mode):
        """Test +code-checks approval command."""
        create_basic_pr_data(
            "test_plus_category_with_hyphen",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "+code-checks",
                    "user": {"login": "cmsbuild", "id": 999},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_plus_category_with_hyphen", record_mode)
        gh = MockGithub("test_plus_category_with_hyphen", recorder)
        repo = MockRepository("test_plus_category_with_hyphen", recorder=recorder)
        issue = MockIssue("test_plus_category_with_hyphen", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # The code-checks category should be approved
        assert "code-checks" in result["categories"]
        assert result["categories"]["code-checks"]["state"] == "approved"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_assign_category_with_hyphen(self, repo_config, record_mode):
        """Test assign command with hyphenated category."""
        create_basic_pr_data(
            "test_assign_category_with_hyphen",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "assign code-checks,l1-trigger",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_assign_category_with_hyphen", record_mode)
        gh = MockGithub("test_assign_category_with_hyphen", recorder)
        repo = MockRepository("test_assign_category_with_hyphen", recorder=recorder)
        issue = MockIssue("test_assign_category_with_hyphen", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_minus_category_with_hyphen(self, repo_config, record_mode):
        """Test -code-checks rejection command."""
        create_basic_pr_data(
            "test_minus_category_with_hyphen",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "-code-checks",
                    "user": {"login": "cmsbuild", "id": 999},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_minus_category_with_hyphen", record_mode)
        gh = MockGithub("test_minus_category_with_hyphen", recorder)
        repo = MockRepository("test_minus_category_with_hyphen", recorder=recorder)
        issue = MockIssue("test_minus_category_with_hyphen", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # The code-checks category should be rejected
        assert "code-checks" in result["categories"]
        assert result["categories"]["code-checks"]["state"] == "rejected"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TYPE COMMAND TESTS
# =============================================================================


class TestTypeCommand:
    """Test the type <label> command."""

    @pytest.fixture
    def repo_config(self):
        """Create a mock repo config with minimal settings."""
        return create_mock_repo_config(
            PRE_CHECKS=[],
            EXTRA_CHECKS=[],
        )

    @pytest.fixture
    def record_mode(self, request):
        """Check if we're in record mode."""
        return request.config.getoption("--record-actions", default=False)

    def test_type_command_adds_label(self, repo_config, record_mode, monkeypatch):
        """Test that type command adds a label to pending_labels."""
        # Mock TYPE_COMMANDS
        mock_type_commands = {
            "bug-fix": ["#ff0000", "bug(?:-?fix)?", "type"],
            "new-feature": ["#00ff00", "(?:new-)?(?:feature|idea)", "type"],
            "documentation": ["#0000ff", "doc(?:umentation)?", "mtype"],
        }
        monkeypatch.setattr("process_pr_v2.TYPE_COMMANDS", mock_type_commands)

        create_basic_pr_data(
            "test_type_command_adds_label",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "type bug-fix",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_type_command_adds_label", record_mode)
        gh = MockGithub("test_type_command_adds_label", recorder)
        repo = MockRepository("test_type_command_adds_label", recorder=recorder)
        issue = MockIssue("test_type_command_adds_label", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert "bug-fix" in result["labels"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_type_label_replaces_previous(self, repo_config, record_mode, monkeypatch):
        """Test that 'type' labels replace each other (only last one applies)."""
        mock_type_commands = {
            "bug-fix": ["#ff0000", "bug(?:-?fix)?", "type"],
            "new-feature": ["#00ff00", "(?:new-)?(?:feature|idea)", "type"],
            "documentation": ["#0000ff", "doc(?:umentation)?", "mtype"],
        }
        monkeypatch.setattr("process_pr_v2.TYPE_COMMANDS", mock_type_commands)

        create_basic_pr_data(
            "test_type_label_replaces_previous",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "type bug-fix",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "type new-feature",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_type_label_replaces_previous", record_mode)
        gh = MockGithub("test_type_label_replaces_previous", recorder)
        repo = MockRepository("test_type_label_replaces_previous", recorder=recorder)
        issue = MockIssue("test_type_label_replaces_previous", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Only the last 'type' label should be present
        assert "new-feature" in result["labels"]
        assert "bug-fix" not in result["labels"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_mtype_labels_accumulate(self, repo_config, record_mode, monkeypatch):
        """Test that 'mtype' labels accumulate (multiple can coexist)."""
        mock_type_commands = {
            "bug-fix": ["#ff0000", "bug(?:-?fix)?", "type"],
            "documentation": ["#0000ff", "doc(?:umentation)?", "mtype"],
            "root": ["#00ff00", "root", "mtype"],
        }
        monkeypatch.setattr("process_pr_v2.TYPE_COMMANDS", mock_type_commands)

        create_basic_pr_data(
            "test_mtype_labels_accumulate",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "type documentation",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "type root",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_mtype_labels_accumulate", record_mode)
        gh = MockGithub("test_mtype_labels_accumulate", recorder)
        repo = MockRepository("test_mtype_labels_accumulate", recorder=recorder)
        issue = MockIssue("test_mtype_labels_accumulate", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Both mtype labels should be present
        assert "documentation" in result["labels"]
        assert "root" in result["labels"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_invalid_type_label(self, repo_config, record_mode, monkeypatch):
        """Test that invalid type labels are rejected."""
        mock_type_commands = {
            "bug-fix": ["#ff0000", "bug(?:-?fix)?", "type"],
        }
        monkeypatch.setattr("process_pr_v2.TYPE_COMMANDS", mock_type_commands)

        create_basic_pr_data(
            "test_invalid_type_label",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "type invalid-label",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_invalid_type_label", record_mode)
        gh = MockGithub("test_invalid_type_label", recorder)
        repo = MockRepository("test_invalid_type_label", recorder=recorder)
        issue = MockIssue("test_invalid_type_label", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert "invalid-label" not in result["labels"]
        # Should have an error message
        assert any("Invalid type label" in msg for msg in result["messages"])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_type_and_mtype_together(self, repo_config, record_mode, monkeypatch):
        """Test type and mtype labels can coexist."""
        mock_type_commands = {
            "bug-fix": ["#ff0000", "bug(?:-?fix)?", "type"],
            "documentation": ["#0000ff", "doc(?:umentation)?", "mtype"],
        }
        monkeypatch.setattr("process_pr_v2.TYPE_COMMANDS", mock_type_commands)

        create_basic_pr_data(
            "test_type_and_mtype_together",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "type bug-fix",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "type documentation",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_type_and_mtype_together", record_mode)
        gh = MockGithub("test_type_and_mtype_together", recorder)
        repo = MockRepository("test_type_and_mtype_together", recorder=recorder)
        issue = MockIssue("test_type_and_mtype_together", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Both type and mtype labels should be present
        assert "bug-fix" in result["labels"]
        assert "documentation" in result["labels"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST DEDUPLICATION
# =============================================================================


class TestTestDeduplication:
    """Test that duplicate test requests are deduplicated."""

    @pytest.fixture
    def repo_config(self):
        """Create a mock repo config."""
        return create_mock_repo_config(
            PRE_CHECKS=[],
            EXTRA_CHECKS=[],
        )

    @pytest.fixture
    def record_mode(self, request):
        """Check if we're in record mode."""
        return request.config.getoption("--record-actions", default=False)

    def test_duplicate_test_commands_deduplicated(self, repo_config, record_mode):
        """Test that identical test commands result in only one test."""
        create_basic_pr_data(
            "test_duplicate_test_commands_deduplicated",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "test",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_duplicate_test_commands_deduplicated", record_mode)
        gh = MockGithub("test_duplicate_test_commands_deduplicated", recorder)
        repo = MockRepository("test_duplicate_test_commands_deduplicated", recorder=recorder)
        issue = MockIssue("test_duplicate_test_commands_deduplicated", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Only one test should be triggered
        assert len(result["tests_triggered"]) == 1
        assert result["tests_triggered"][0]["verb"] == "test"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_different_verb_not_deduplicated(self, repo_config, record_mode):
        """Test that build and test are treated as different."""
        create_basic_pr_data(
            "test_different_verb_not_deduplicated",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "build",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_different_verb_not_deduplicated", record_mode)
        gh = MockGithub("test_different_verb_not_deduplicated", recorder)
        repo = MockRepository("test_different_verb_not_deduplicated", recorder=recorder)
        issue = MockIssue("test_different_verb_not_deduplicated", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Both test and build should be triggered
        assert len(result["tests_triggered"]) == 2
        verbs = {t["verb"] for t in result["tests_triggered"]}
        assert verbs == {"test", "build"}

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_different_workflows_not_deduplicated(self, repo_config, record_mode):
        """Test that tests with different workflows are not deduplicated."""
        create_basic_pr_data(
            "test_different_workflows_not_deduplicated",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test workflows 1.0",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "test workflows 2.0",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_different_workflows_not_deduplicated", record_mode)
        gh = MockGithub("test_different_workflows_not_deduplicated", recorder)
        repo = MockRepository("test_different_workflows_not_deduplicated", recorder=recorder)
        issue = MockIssue("test_different_workflows_not_deduplicated", number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Both tests should be triggered
        assert len(result["tests_triggered"]) == 2

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_same_workflows_different_order_deduplicated(self, repo_config, record_mode):
        """Test that same workflows in different order are deduplicated."""
        create_basic_pr_data(
            "test_same_workflows_different_order_deduplicated",
            pr_number=1,
            files=[
                {
                    "filename": "src/core/main.py",
                    "sha": "file_sha_123",
                    "status": "modified",
                }
            ],
            comments=[
                {
                    "id": 100,
                    "body": "test workflows 1.0,2.0",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
                {
                    "id": 101,
                    "body": "test workflows 2.0,1.0",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.now(tz=timezone.utc).isoformat(),
                },
            ],
        )

        recorder = ActionRecorder("test_same_workflows_different_order_deduplicated", record_mode)
        gh = MockGithub("test_same_workflows_different_order_deduplicated", recorder)
        repo = MockRepository(
            "test_same_workflows_different_order_deduplicated", recorder=recorder
        )
        issue = MockIssue(
            "test_same_workflows_different_order_deduplicated", number=1, recorder=recorder
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Only one test should be triggered (same workflows, different order)
        assert len(result["tests_triggered"]) == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: TEST PARAMETERS COMMAND
# =============================================================================


class TestTestParametersCommand:
    """Tests for the 'test parameters:' multiline command."""

    def test_parse_test_parameters_basic(self):
        """Test basic parameter parsing."""
        lines = [
            "test parameters:",
            "- workflows = 1.0,2.0,3.0",
            "- pull_requests = #1234,#5678",
        ]

        # Create a mock repo
        mock_repo = MagicMock()
        mock_repo.full_name = "cms-sw/cmssw"

        result = parse_test_parameters(lines, mock_repo)

        assert "errors" not in result
        assert "MATRIX_EXTRAS" in result
        assert "PULL_REQUESTS" in result

    def test_parse_test_parameters_with_list_markers(self):
        """Test that list markers (- and *) are properly stripped."""
        lines = [
            "test parameters:",
            "- full_cmssw = true",
            "* dry_run = false",
        ]

        mock_repo = MagicMock()
        mock_repo.full_name = "cms-sw/cmssw"

        result = parse_test_parameters(lines, mock_repo)

        assert "errors" not in result
        assert result.get("BUILD_FULL_CMSSW") == "true"
        assert result.get("DRY_RUN") == "false"

    def test_parse_test_parameters_invalid_key(self):
        """Test that invalid keys are reported as errors."""
        lines = [
            "test parameters:",
            "- invalid_key = some_value",
        ]

        mock_repo = MagicMock()
        mock_repo.full_name = "cms-sw/cmssw"

        result = parse_test_parameters(lines, mock_repo)

        assert "errors" in result
        assert "key:" in result["errors"]

    def test_parse_test_parameters_invalid_format(self):
        """Test that lines without = are reported as format errors."""
        lines = [
            "test parameters:",
            "- this line has no equals sign",
        ]

        mock_repo = MagicMock()
        mock_repo.full_name = "cms-sw/cmssw"

        result = parse_test_parameters(lines, mock_repo)

        assert "errors" in result
        assert "format:" in result["errors"]

    def test_parse_test_parameters_release_format(self):
        """Test release format with architecture."""
        lines = [
            "test parameters:",
            "- release = CMSSW_14_0_X/el8_amd64_gcc12",
        ]

        mock_repo = MagicMock()
        mock_repo.full_name = "cms-sw/cmssw"

        result = parse_test_parameters(lines, mock_repo)

        assert "errors" not in result
        # check_release_format extracts architecture
        assert "ARCHITECTURE_FILTER" in result


# =============================================================================
# TEST: VALID TESTER ACL
# =============================================================================


class TestValidTesterACL:
    """Tests for the is_valid_tester ACL function."""

    def test_trigger_pr_tests_user_is_valid(self, monkeypatch):
        """Test that users in TRIGGER_PR_TESTS are valid testers."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", ["test_user"])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.repo_config = MagicMock()
        context.granted_test_rights = set()

        # Mock get_release_managers to return empty
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: [])
        # Mock get_user_l2_categories to return empty
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: [])

        assert is_valid_tester(context, "test_user", datetime.now(tz=timezone.utc))

    def test_release_manager_is_valid(self, monkeypatch):
        """Test that release managers are valid testers."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", [])
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: ["release_mgr"])
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: [])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.granted_test_rights = set()

        assert is_valid_tester(context, "release_mgr", datetime.now(tz=timezone.utc))

    def test_l2_signer_is_valid(self, monkeypatch):
        """Test that L2 signers are valid testers."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", [])
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: [])
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: ["core"])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.repo_config = MagicMock()
        context.granted_test_rights = set()

        assert is_valid_tester(context, "l2_user", datetime.now(tz=timezone.utc))

    def test_granted_test_rights_is_valid(self, monkeypatch):
        """Test that users with granted test rights are valid testers."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", [])
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: [])
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: [])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.repo_config = MagicMock()
        context.granted_test_rights = {"granted_user"}

        assert is_valid_tester(context, "granted_user", datetime.now(tz=timezone.utc))

    def test_random_user_not_valid(self, monkeypatch):
        """Test that random users are not valid testers."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", [])
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: [])
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: [])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.repo_config = MagicMock()
        context.granted_test_rights = set()

        assert not is_valid_tester(context, "random_user", datetime.now(tz=timezone.utc))

    def test_repo_org_is_valid(self, monkeypatch):
        """Test that the repo organization is a valid tester."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", [])
        monkeypatch.setattr("process_pr_v2.get_release_managers", lambda x: [])
        monkeypatch.setattr("process_pr_v2.get_user_l2_categories", lambda *args: [])

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.base.ref = "master"
        context.repo_org = "cms-sw"
        context.granted_test_rights = set()

        assert is_valid_tester(context, "cms-sw", datetime.now(tz=timezone.utc))


# =============================================================================
# TEST: COMMIT AND FILE COUNT CHECKS
# =============================================================================


class TestCommitAndFileCountChecks:
    """Tests for commit and file count threshold checks."""

    def test_normal_pr_not_blocked(self):
        """Test that PRs with normal counts are not blocked."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = 10
        context.pr.changed_files = 50
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = True
        context.warned_too_many_commits = False
        context.warned_too_many_files = False
        context.ignore_commit_count = False
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        assert result is None  # Not blocked

    def test_too_many_commits_blocks_pr(self):
        """Test that PRs with too many commits are blocked."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = TOO_MANY_COMMITS_WARN_THRESHOLD + 10
        context.pr.changed_files = 50
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = False
        context.warned_too_many_commits = False
        context.warned_too_many_files = False
        context.ignore_commit_count = False
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        assert result is not None
        assert result["blocked"] is True
        assert "commits" in result["reason"].lower()

    def test_commit_count_override_unblocks(self):
        """Test that +commit-count override unblocks PR."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = TOO_MANY_COMMITS_WARN_THRESHOLD + 10
        context.pr.changed_files = 50
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = False
        context.warned_too_many_commits = True
        context.warned_too_many_files = False
        context.ignore_commit_count = True  # Override given
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        assert result is None  # Not blocked due to override

    def test_too_many_files_blocks_cmssw_repo(self):
        """Test that PRs with too many files are blocked (CMSSW repo only)."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = 10
        context.pr.changed_files = TOO_MANY_FILES_WARN_THRESHOLD + 100
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = True  # Only blocks for CMSSW repo
        context.warned_too_many_commits = False
        context.warned_too_many_files = False
        context.ignore_commit_count = False
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        assert result is not None
        assert result["blocked"] is True
        assert "files" in result["reason"].lower()

    def test_too_many_files_not_blocked_external_repo(self):
        """Test that file count doesn't block external repos."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = 10
        context.pr.changed_files = TOO_MANY_FILES_WARN_THRESHOLD + 100
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = False  # External repo
        context.warned_too_many_commits = False
        context.warned_too_many_files = False
        context.ignore_commit_count = False
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        assert result is None  # Not blocked for external repos

    def test_fail_threshold_cannot_be_overridden(self):
        """Test that counts at FAIL threshold cannot be overridden."""
        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.commits = TOO_MANY_COMMITS_FAIL_THRESHOLD + 10
        context.pr.changed_files = 50
        context.issue = MagicMock()
        context.issue.number = 1
        context.comments = []
        context.cmssw_repo = False
        context.warned_too_many_commits = False
        context.warned_too_many_files = False
        context.ignore_commit_count = True  # Override attempted
        context.ignore_file_count = False
        context.notify_without_at = False

        result = check_commit_and_file_counts(context, dryRun=True)

        # Still blocked even with override because at FAIL threshold
        assert result is not None
        assert result["blocked"] is True


# =============================================================================
# TEST: CLOSE AND REOPEN COMMANDS
# =============================================================================


class TestCloseReopenCommands:
    """Tests for close and reopen commands."""

    def test_close_command(self, record_mode):
        """Test that close command sets must_close."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_close_command", record_mode)
        gh = MockGithub("test_close_command", recorder)
        repo = MockRepository("test_close_command", recorder=recorder)
        issue = MockIssue(
            "test_close_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "l2_user"},
                    "body": "close",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        # The close command should have been processed
        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_reopen_command(self, record_mode):
        """Test that reopen command is processed."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_reopen_command", record_mode)
        gh = MockGithub("test_reopen_command", recorder)
        repo = MockRepository("test_reopen_command", recorder=recorder)
        issue = MockIssue(
            "test_reopen_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "l2_user"},
                    "body": "reopen",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: ABORT COMMAND
# =============================================================================


class TestAbortCommand:
    """Tests for abort test command."""

    def test_abort_command(self, record_mode, monkeypatch):
        """Test that abort command sets abort_tests flag."""
        # Make the user a valid tester
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", ["tester"])

        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_abort_command", record_mode)
        gh = MockGithub("test_abort_command", recorder)
        repo = MockRepository("test_abort_command", recorder=recorder)
        issue = MockIssue(
            "test_abort_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "tester"},
                    "body": "abort",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_abort_test_command(self, record_mode, monkeypatch):
        """Test that 'abort test' command also works."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", ["tester"])

        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_abort_test_command", record_mode)
        gh = MockGithub("test_abort_test_command", recorder)
        repo = MockRepository("test_abort_test_command", recorder=recorder)
        issue = MockIssue(
            "test_abort_test_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "tester"},
                    "body": "abort test",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: URGENT AND BACKPORT COMMANDS
# =============================================================================


class TestUrgentBackportCommands:
    """Tests for urgent and backport commands."""

    def test_urgent_command_adds_label(self, record_mode):
        """Test that urgent command adds the urgent label."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_urgent_command", record_mode)
        gh = MockGithub("test_urgent_command", recorder)
        repo = MockRepository("test_urgent_command", recorder=recorder)
        issue = MockIssue(
            "test_urgent_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "l2_user"},
                    "body": "urgent",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        # Check that urgent label was added
        assert "urgent" in result.get("labels", [])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_backport_command_adds_label(self, record_mode):
        """Test that backport command adds the backport label."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_backport_command", record_mode)
        gh = MockGithub("test_backport_command", recorder)
        repo = MockRepository("test_backport_command", recorder=recorder)
        issue = MockIssue(
            "test_backport_command",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "l2_user"},
                    "body": "backport of #5678",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1
        assert "backport" in result.get("labels", [])

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: ALLOW TEST RIGHTS COMMAND
# =============================================================================


class TestAllowTestRightsCommand:
    """Tests for 'allow @user test rights' command."""

    def test_allow_test_rights_grants_access(self, record_mode):
        """Test that allow test rights command grants test access."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_allow_test_rights", record_mode)
        gh = MockGithub("test_allow_test_rights", recorder)
        repo = MockRepository("test_allow_test_rights", recorder=recorder)
        issue = MockIssue(
            "test_allow_test_rights",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "l2_user"},  # L2 user can grant rights
                    "body": "allow @newuser test rights",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: CODE CHECKS COMMAND
# =============================================================================


class TestCodeChecksCommand:
    """Tests for code-checks command."""

    def test_code_checks_basic(self, record_mode):
        """Test basic code-checks command."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_code_checks_basic", record_mode)
        gh = MockGithub("test_code_checks_basic", recorder)
        repo = MockRepository("test_code_checks_basic", recorder=recorder)
        issue = MockIssue(
            "test_code_checks_basic",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "contributor"},
                    "body": "code-checks",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_code_checks_with_tool_conf(self, record_mode):
        """Test code-checks with tool configuration."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_code_checks_with_tool", record_mode)
        gh = MockGithub("test_code_checks_with_tool", recorder)
        repo = MockRepository("test_code_checks_with_tool", recorder=recorder)
        issue = MockIssue(
            "test_code_checks_with_tool",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "contributor"},
                    "body": "code-checks with cms.week0.PR_abc12345/some-config",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: IGNORE TESTS REJECTED COMMAND
# =============================================================================


class TestIgnoreTestsRejectedCommand:
    """Tests for 'ignore tests-rejected with <reason>' command."""

    def test_ignore_tests_rejected_manual_override(self, record_mode, monkeypatch):
        """Test ignore tests-rejected with manual-override reason."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", ["tester"])

        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_ignore_tests_rejected", record_mode)
        gh = MockGithub("test_ignore_tests_rejected", recorder)
        repo = MockRepository("test_ignore_tests_rejected", recorder=recorder)
        issue = MockIssue(
            "test_ignore_tests_rejected",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "tester"},
                    "body": "ignore tests-rejected with manual-override",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_ignore_tests_rejected_ib_failure(self, record_mode, monkeypatch):
        """Test ignore tests-rejected with ib-failure reason."""
        monkeypatch.setattr("process_pr_v2.TRIGGER_PR_TESTS", ["tester"])

        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_ignore_tests_ib_failure", record_mode)
        gh = MockGithub("test_ignore_tests_ib_failure", recorder)
        repo = MockRepository("test_ignore_tests_ib_failure", recorder=recorder)
        issue = MockIssue(
            "test_ignore_tests_ib_failure",
            number=1,
            recorder=recorder,
            comments_data=[
                {
                    "id": 1001,
                    "user": {"login": "tester"},
                    "body": "ignore tests-rejected with ib-failure",
                    "created_at": "2024-01-15T12:00:00Z",
                },
            ],
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: PROPERTIES FILE CREATION
# =============================================================================


class TestPropertiesFileCreation:
    """Tests for properties file creation functions."""

    def test_create_property_file_dry_run(self, tmp_path):
        """Test that dry run doesn't create file."""
        filename = str(tmp_path / "test.properties")
        params = {"KEY1": "value1", "KEY2": "value2"}

        create_property_file(filename, params, dry_run=True)

        assert not os.path.exists(filename)

    def test_create_property_file_actual(self, tmp_path):
        """Test actual file creation."""
        filename = str(tmp_path / "test.properties")
        params = {"KEY1": "value1", "KEY2": "value2"}

        create_property_file(filename, params, dry_run=False)

        assert os.path.exists(filename)
        with open(filename) as f:
            content = f.read()
        assert "KEY1=value1" in content
        assert "KEY2=value2" in content

    def test_build_test_parameters(self):
        """Test building test parameters from request."""
        context = MagicMock(spec=PRContext)
        context.repo_org = "cms-sw"
        context.repo_name = "cmssw"
        context.issue = MagicMock()
        context.issue.number = 1234
        context.test_params = {"EXISTING_PARAM": "existing_value"}

        test_request = TestRequest(
            verb="test",
            workflows="1.0,2.0",
            prs=["cms-sw/cmsdist#100"],
            queue="CMSSW_14_0_X",
            build_full=True,
            extra_packages="Package/SubPkg",
            triggered_by="user",
            comment_id=1001,
        )

        params = build_test_parameters(context, test_request)

        assert "cms-sw/cmssw#1234" in params["PULL_REQUESTS"]
        assert "cms-sw/cmsdist#100" in params["PULL_REQUESTS"]
        assert params["MATRIX_EXTRAS"] == "1.0,2.0"
        assert params["RELEASE_FORMAT"] == "CMSSW_14_0_X"
        assert params["BUILD_FULL_CMSSW"] == "true"
        assert params["EXTRA_CMSSW_PACKAGES"] == "Package/SubPkg"
        assert params["EXISTING_PARAM"] == "existing_value"

    def test_build_test_parameters_build_only(self):
        """Test that build verb sets BUILD_ONLY flag."""
        context = MagicMock(spec=PRContext)
        context.repo_org = "cms-sw"
        context.repo_name = "cmssw"
        context.issue = MagicMock()
        context.issue.number = 1234
        context.test_params = {}

        test_request = TestRequest(
            verb="build",  # build, not test
            workflows="",
            prs=[],
            queue="",
            build_full=False,
            extra_packages="",
            triggered_by="user",
            comment_id=1001,
        )

        params = build_test_parameters(context, test_request)

        assert params.get("BUILD_ONLY") == "true"


# =============================================================================
# TEST: COMMAND PREPROCESSING
# =============================================================================


class TestCommandPreprocessingWhitespace:
    """Tests for command preprocessing whitespace handling."""

    def test_multiple_spaces_collapsed(self):
        """Test that multiple spaces are collapsed to single space."""
        result = preprocess_command("test   parameters")
        assert result == "test parameters"
        assert "  " not in result

    def test_tabs_converted_to_space(self):
        """Test that tabs are converted to spaces."""
        result = preprocess_command("test\tparameters")
        assert result == "test parameters"

    def test_leading_trailing_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        result = preprocess_command("  +1  ")
        assert result == "+1"

    def test_spaces_around_commas_removed(self):
        """Test that spaces around commas are removed."""
        result = preprocess_command("assign cat1 , cat2 , cat3")
        assert result == "assign cat1,cat2,cat3"

    def test_cmsbuild_prefix_removed(self):
        """Test that @cmsbuild prefix is removed."""
        result = preprocess_command("@cmsbuild please +1")
        assert result == "+1"

    def test_please_prefix_removed(self):
        """Test that 'please' prefix is removed."""
        result = preprocess_command("please test")
        assert result == "test"


# =============================================================================
# TEST: DRAFT PR HANDLING
# =============================================================================


class TestDraftPRHandling:
    """Tests for draft PR handling."""

    def test_draft_pr_disables_at_mentions(self):
        """Test that draft PRs disable @-mentions."""
        context = MagicMock(spec=PRContext)
        context.notify_without_at = False
        context.is_draft = True  # This is now a property but we mock it

        # Mock the property
        type(context).is_draft = property(lambda self: True)

        result = format_mention(context, "testuser")
        assert result == "testuser"
        assert "@" not in result

    def test_non_draft_pr_has_at_mentions(self):
        """Test that non-draft PRs have @-mentions."""
        context = MagicMock(spec=PRContext)
        context.notify_without_at = False
        type(context).is_draft = property(lambda self: False)

        result = format_mention(context, "testuser")
        assert result == "@testuser"

    def test_notify_without_at_overrides(self):
        """Test that notify_without_at flag overrides draft status."""
        context = MagicMock(spec=PRContext)
        context.notify_without_at = True
        type(context).is_draft = property(lambda self: False)

        result = format_mention(context, "testuser")
        assert result == "testuser"


# =============================================================================
# TEST: WELCOME MESSAGE
# =============================================================================


class TestWelcomeMessage:
    """Tests for welcome message generation."""

    def test_welcome_message_contains_author(self, record_mode):
        """Test that welcome message contains author mention."""
        repo_config = create_mock_repo_config()
        init_l2_data(repo_config)

        recorder = ActionRecorder("test_welcome_message_author", record_mode)
        gh = MockGithub("test_welcome_message_author", recorder)
        repo = MockRepository("test_welcome_message_author", recorder=recorder)
        issue = MockIssue(
            "test_welcome_message_author",
            number=1,
            recorder=recorder,
            comments_data=[],  # No existing comments
        )

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            loglevel="WARNING",
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


# =============================================================================
# TEST: CI TEST STATUS
# =============================================================================


class TestCITestStatus:
    """Tests for CI test status detection."""

    def test_get_ci_test_statuses_no_pr(self):
        """Test get_ci_test_statuses with no PR."""
        from process_pr_v2 import get_ci_test_statuses

        context = MagicMock(spec=PRContext)
        context.pr = None
        context.commits = []

        result = get_ci_test_statuses(context)
        assert result == {}

    def test_get_ci_test_statuses_no_commits(self):
        """Test get_ci_test_statuses with no commits."""
        from process_pr_v2 import get_ci_test_statuses

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.commits = []
        context.pr.head.sha = "abc123"
        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = []

        result = get_ci_test_statuses(context)
        assert result == {}

    def test_get_ci_test_statuses_with_required(self):
        """Test get_ci_test_statuses with required test status."""
        from process_pr_v2 import get_ci_test_statuses

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.head.sha = "abc123"
        context.commits = [MagicMock(sha="abc123")]

        # Create mock statuses
        status1 = MagicMock()
        status1.context = "cms/el8_amd64_gcc12/build/required"
        status1.state = "success"
        status1.description = "Build successful"
        status1.target_url = "http://example.com/build"

        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = [status1]

        result = get_ci_test_statuses(context)
        assert "required" in result
        assert len(result["required"]) == 1
        assert result["required"][0].context == "cms/el8_amd64_gcc12/build/required"

    def test_get_ci_test_statuses_with_optional(self):
        """Test get_ci_test_statuses with optional test status."""
        from process_pr_v2 import get_ci_test_statuses

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.head.sha = "abc123"
        context.commits = [MagicMock(sha="abc123")]

        # Create mock statuses
        status1 = MagicMock()
        status1.context = "cms/el8_amd64_gcc12/relvals/optional"
        status1.state = "pending"
        status1.description = "Running tests"
        status1.target_url = "http://example.com/relvals"

        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = [status1]

        result = get_ci_test_statuses(context)
        assert "optional" in result
        assert len(result["optional"]) == 1
        assert result["optional"][0].is_optional is True

    def test_check_ci_test_completion_pending(self):
        """Test check_ci_test_completion with pending tests."""
        from process_pr_v2 import check_ci_test_completion

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.head.sha = "abc123"
        context.commits = [MagicMock(sha="abc123")]

        # Create mock statuses with pending state
        status1 = MagicMock()
        status1.context = "cms/el8_amd64_gcc12/build/required"
        status1.state = "pending"
        status1.description = "Running"
        status1.target_url = None

        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = [status1]

        result = check_ci_test_completion(context)
        # Pending tests should return None or empty dict
        assert result is None or "required" not in result

    def test_check_ci_test_completion_success(self):
        """Test check_ci_test_completion with successful tests."""
        from process_pr_v2 import check_ci_test_completion

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.head.sha = "abc123"
        context.commits = [MagicMock(sha="abc123")]

        # Create mock statuses with success state
        status1 = MagicMock()
        status1.context = "cms/el8_amd64_gcc12/build/required"
        status1.state = "success"
        status1.description = "Finished"
        status1.target_url = "http://example.com/build"

        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = [status1]

        result = check_ci_test_completion(context)
        assert result is not None
        assert result.get("required") == "success"

    def test_check_ci_test_completion_error(self):
        """Test check_ci_test_completion with failed tests."""
        from process_pr_v2 import check_ci_test_completion

        context = MagicMock(spec=PRContext)
        context.pr = MagicMock()
        context.pr.head.sha = "abc123"
        context.commits = [MagicMock(sha="abc123")]

        # Create mock statuses with error state
        status1 = MagicMock()
        status1.context = "cms/el8_amd64_gcc12/build/required"
        status1.state = "error"
        status1.description = "Build failed"
        status1.target_url = "http://example.com/build"

        context.repo = MagicMock()
        context.repo.get_commit.return_value.get_statuses.return_value = [status1]

        result = check_ci_test_completion(context)
        assert result is not None
        assert result.get("required") == "error"


# =============================================================================
# CONFTEST HOOK FOR PYTEST OPTIONS
# =============================================================================

# This needs to be in conftest.py for pytest to pick it up, but we include
# it here for convenience when running the file directly


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "record_actions: mark test to record actions")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


if __name__ == "__main__":
    # Allow running directly for debugging
    import sys

    # Check for --record-actions flag
    record = "--record-actions" in sys.argv

    # Run pytest
    args = [__file__, "-v"]
    if record:
        args.append("--record-actions")

    pytest.main(args)
