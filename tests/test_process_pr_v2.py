#!/usr/bin/env python3
"""
PyTest tests for cms-bot process_pr function.

This test module provides:
- Mock implementations of PyGithub classes that load state from JSON files
- Recording mode to capture actions for later comparison
- Comparison mode to verify actions match expected results

Usage:
    # Run tests in comparison mode (default)
    pytest test_process_pr.py

    # Run tests in recording mode (saves actions to PRActionData/)
    pytest test_process_pr.py --record-actions

    # Run a specific test
    pytest test_process_pr.py::test_basic_approval --record-actions
"""

import json
import os
import pytest
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from unittest.mock import MagicMock

# Import the module under test
from cms_bot import (
    process_pr,
    ApprovalState,
    PRState,
    BotCache,
    FileVersion,
    Snapshot,
    CommentInfo,
    TestRequest,
    TestCmdResult,
    parse_test_cmd,
    TestCmdParseError,
    should_ignore_pr,
    should_notify_without_at,
    format_mention,
    EXAMPLE_REPO_CONFIG,
)


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Base directories for test data
REPLAY_DATA_DIR = Path(__file__).parent / "ReplayData"
ACTION_DATA_DIR = Path(__file__).parent / "PRActionData"


def pytest_addoption(parser):
    """Add command-line option for recording mode."""
    parser.addoption(
        "--record-actions",
        action="store_true",
        default=False,
        help="Record actions instead of comparing to saved data",
    )


@pytest.fixture
def record_mode(request):
    """Fixture to check if we're in recording mode."""
    return request.config.getoption("--record-actions")


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

    def verify(self) -> None:
        """Verify recorded actions match expected."""
        expected = self.load_expected()

        # Compare action counts
        assert len(self.actions) == len(expected), (
            f"Action count mismatch: got {len(self.actions)}, " f"expected {len(expected)}"
        )

        # Compare each action
        for i, (actual, exp) in enumerate(zip(self.actions, expected)):
            assert actual["action"] == exp["action"], (
                f"Action {i + 1} type mismatch: "
                f"got '{actual['action']}', expected '{exp['action']}'"
            )

            # Compare details (allowing for some flexibility)
            for key, exp_value in exp.get("details", {}).items():
                actual_value = actual.get("details", {}).get(key)
                assert actual_value == exp_value, (
                    f"Action {i + 1} ({actual['action']}) detail '{key}' mismatch: "
                    f"got {actual_value!r}, expected {exp_value!r}"
                )


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
            date: datetime = field(default_factory=datetime.utcnow)
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
            date=datetime.fromisoformat(author_data.get("date", datetime.utcnow().isoformat())),
            name=author_data.get("name", ""),
            email=author_data.get("email", ""),
        )

        git_committer = cls.GitCommit.GitAuthor(
            date=datetime.fromisoformat(committer_data.get("date", datetime.utcnow().isoformat())),
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
class MockFile:
    """Mock for github.File.File (PR file)"""

    filename: str
    sha: str
    status: str = "modified"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str = ""

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
        self.updated_at = datetime.utcnow()

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
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.utcnow().isoformat())
            ),
            updated_at=(
                datetime.fromisoformat(data.get("updated_at", datetime.utcnow().isoformat()))
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

        # Load related data
        self._files = self._load_files(data.get("files", []))
        self._commits = self._load_commits(data.get("commits", []))

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
            created_at=datetime.utcnow(),
            _recorder=self._recorder,
        )


class MockIssue:
    """Mock for github.Issue.Issue"""

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
        data = load_json_data(test_name, "Issue", number)

        self.id = data.get("id", number)
        self.title = data.get("title", f"Issue #{number}")
        self.body = data.get("body", "")
        self.state = data.get("state", "open")

        # User
        user_data = data.get("user", {"login": "author"})
        self.user = MockNamedUser.from_json(user_data)

        # Labels
        self._labels = [MockLabel.from_json(l) for l in data.get("labels", [])]

        # Comments
        self._comments = self._load_comments(data.get("comments", []))

        # Associated PR (if this is a PR issue)
        self._pull_request = None

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
            created_at=datetime.utcnow(),
            _recorder=self._recorder,
        )
        self._comments.append(comment)
        return comment

    def as_pull_request(self) -> MockPullRequest:
        """Convert issue to pull request."""
        if self._pull_request is None:
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
    """Get default repository configuration."""
    return EXAMPLE_REPO_CONFIG.copy()


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
                        "date": datetime.utcnow().isoformat(),
                        "name": "Test Author",
                        "email": "test@example.com",
                    },
                    "committer": {
                        "date": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
                },
                {
                    "id": 101,
                    "body": "hold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
                },
                {
                    "id": 101,
                    "body": "unhold",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
                },
                {
                    "id": 101,
                    "body": "hold",
                    "user": {"login": "bob", "id": 3},
                    "created_at": datetime.utcnow().isoformat(),
                },
                {
                    "id": 102,
                    "body": "unhold",
                    "user": {"login": "dave", "id": 4},  # dave is ORP
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_please_prefix_removal(self, repo_config, record_mode):
        """Test that 'please' prefix is properly removed."""
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
                    "body": "please test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
                }
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
            enableTraceLog=False,
        )

        assert "default" in result["tests_triggered"]

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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "body": "test",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
                }
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
            enableTraceLog=False,
        )

        assert "default" in result["tests_triggered"]

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_with_params(self, repo_config, record_mode):
        """Test trigger with parameters."""
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
                    "body": "test workflow=ci matrix=full",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
                }
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
            enableTraceLog=False,
        )

        assert "workflow=ci matrix=full" in result["tests_triggered"]

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
            enableTraceLog=False,
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
        # Disable ORP requirement for this test
        config = repo_config.copy()
        config["require_orp"] = False
        config["require_tests"] = False
        config["require_code_checks"] = False

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
                    "created_at": datetime.utcnow().isoformat(),
                },
                {
                    "id": 101,
                    "body": "merge",
                    "user": {"login": "alice", "id": 2},
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
        )

        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_ci_approval(self, repo_config, record_mode):
        """Test that +1 from bot (CI results) is processed when bot has L2 categories."""
        # Update config to give bot the 'tests' category
        config = repo_config.copy()
        config["user_teams"] = repo_config["user_teams"].copy()
        config["user_teams"]["cmsbuild"] = ["tests", "code-checks"]

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
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_ci_approval", record_mode)
        gh = MockGithub("test_bot_ci_approval", recorder)
        repo = MockRepository("test_bot_ci_approval", recorder=recorder)
        issue = MockIssue("test_bot_ci_approval", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            enableTraceLog=False,
        )

        assert result["pr_number"] == 1
        # The +1 should be processed for bot's L2 categories (tests, code-checks)

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_bot_category_specific_approval(self, repo_config, record_mode):
        """Test that +tests from bot is processed."""
        config = repo_config.copy()
        config["user_teams"] = repo_config["user_teams"].copy()
        config["user_teams"]["cmsbuild"] = ["tests", "code-checks"]

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
                    "created_at": datetime.utcnow().isoformat(),
                }
            ],
        )

        recorder = ActionRecorder("test_bot_category_specific_approval", record_mode)
        gh = MockGithub("test_bot_category_specific_approval", recorder)
        repo = MockRepository("test_bot_category_specific_approval", recorder=recorder)
        issue = MockIssue("test_bot_category_specific_approval", number=1, recorder=recorder)

        result = process_pr(
            repo_config=config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=True,
            cmsbuild_user="cmsbuild",
            enableTraceLog=False,
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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
        """Test parsing 'test for rhel8-amd64'."""
        result = parse_test_cmd("test for rhel8-amd64")
        assert result.verb == "test"
        assert result.queue == "rhel8-amd64"

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
        result = parse_test_cmd("build workflows 1.0,2.0 with #123 for rhel8 using full cmssw")
        assert result.verb == "build"
        assert result.workflows == ["1.0", "2.0"]
        assert result.prs == ["#123"]
        assert result.queue == "rhel8"
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
        # Remove required signatures for this test
        config = repo_config.copy()
        config["required_signatures_for_test"] = []

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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
        )

        assert result["pr_number"] == 1
        assert len(result["tests_triggered"]) == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_command_with_workflows(self, repo_config, record_mode):
        """Test test command with workflows parameter."""
        config = repo_config.copy()
        config["required_signatures_for_test"] = []

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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
        )

        assert result["pr_number"] == 1
        assert len(result["tests_triggered"]) == 1
        # Check that the TestRequest has workflows
        test_req = result["tests_triggered"][0]
        assert "1.0" in test_req.workflows

        if record_mode:
            recorder.save()
        else:
            recorder.verify()

    def test_test_blocked_by_missing_signature(self, repo_config, record_mode):
        """Test that test is blocked when required signature is missing."""
        config = repo_config.copy()
        config["required_signatures_for_test"] = ["code-checks"]

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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
    """Tests for PR description parsing (<cms-bot>, <notify> tags)."""

    def test_should_ignore_pr_with_cms_bot_tag(self):
        """Test that <cms-bot></cms-bot> tag is detected."""
        assert should_ignore_pr("<cms-bot></cms-bot>") is True
        assert should_ignore_pr("<cms-bot> </cms-bot>") is True
        assert should_ignore_pr("<CMS-BOT></CMS-BOT>") is True
        assert should_ignore_pr("  <cms-bot></cms-bot>  ") is True

    def test_should_not_ignore_pr_without_tag(self):
        """Test that PRs without the tag are not ignored."""
        assert should_ignore_pr("") is False
        assert should_ignore_pr("Normal PR description") is False
        assert should_ignore_pr("Fix bug in module\n\nDetails here") is False
        assert should_ignore_pr("<cms-bot>content</cms-bot>") is False  # Has content

    def test_should_not_ignore_pr_with_tag_not_on_first_line(self):
        """Test that tag must be on first non-blank line."""
        assert should_ignore_pr("Some text\n<cms-bot></cms-bot>") is False
        assert should_ignore_pr("\n\nSome text\n<cms-bot></cms-bot>") is False

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
                    "created_at": datetime.utcnow().isoformat(),
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
            enableTraceLog=False,
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
            enableTraceLog=False,
        )

        # Should NOT be skipped because force=True
        assert result.get("skipped") is not True
        assert result["pr_number"] == 1

        if record_mode:
            recorder.save()
        else:
            recorder.verify()


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
