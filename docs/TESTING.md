# Adding Tests to process_pr

## Quick Start

### Standard Test Pattern

Every test follows this structure:

```python
class TestMyFeature:
    def test_my_scenario(self, test_name, alice_user, repo_config, record_mode):
        """Short description of what this tests."""
        create_basic_pr_data(
            test_name,
            comments=[
                {"id": 100, "body": "+1"},   # user filled in from alice_user below
            ],
            user=alice_user,
        )

        recorder = ActionRecorder(test_name, record_mode)
        gh = MockGithub(test_name, recorder)
        repo = MockRepository(test_name, recorder=recorder)
        issue = MockIssue(test_name, number=1, recorder=recorder)

        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=False,
            cmsbuild_user="cmsbuild",
            loglevel="DEBUG",
        )

        assert result["pr_number"] == 1
        assert result["categories"]["core"]["state"] == "approved"

        if record_mode:
            recorder.save()
        else:
            recorder.verify()
```

### Record Expected Actions

Run once in record mode to capture expected actions:

```bash
pytest test_process_pr_v2.py::TestMyFeature::test_my_scenario --record-actions
```

This creates `ReplayData/test_my_scenario/actions.json`. Commit it alongside the test.

### Run in Verify Mode

```bash
pytest test_process_pr_v2.py::TestMyFeature::test_my_scenario
# or all tests:
pytest test_process_pr_v2.py
```

---

## `create_basic_pr_data()` Reference

Creates all JSON fixture files needed to run `process_pr` against a mock PR.
Must be called before constructing any Mock objects for the same test.

```python
def create_basic_pr_data(
    test_name: str,
    pr_number: int = 1,
    files: List[Dict] = None,
    comments: List[Dict] = None,
    commits: List[Dict] = None,
    labels: List[str] = None,
    base_ref: str = "main",
    statuses: List[Dict] = None,
    login: str = "testuser",
    user: Dict[str, Any] = None,
) -> None:
```

### Parameters

#### `test_name: str`
The test's name — use the `test_name` fixture (automatically set to the method name).
Determines the directory where fixture files are written: `ReplayData/<test_name>/`.

```python
def test_something(self, test_name, ...):
    create_basic_pr_data(test_name, ...)   # always pass test_name first
```

#### `pr_number: int = 1`
GitHub PR/Issue number. Used as the ID in all generated JSON files.
Only needs to change if the test involves multiple PRs.

#### `files: List[Dict] = None`
Files changed in the PR. Each dict must have `filename`, `sha`, and `status`.
The `filename` is matched against `CMSSW_CATEGORIES` to determine which L2 categories
are required.

```python
files=[
    {
        "filename": "Package/Core/myfile.cc",  # maps to 'core' category
        "sha": "abc123",                        # blob SHA (determines signature validity)
        "status": "modified",                   # "modified", "added", or "deleted"
    },
    {
        "filename": "Package/Simulation/sim.cc",
        "sha": "def456",
        "status": "added",
    },
]
```

**Default** (when `None`): a single modified `Package/Core/main.py` file, which maps
to the `core` category.

**Test categories → packages mapping** (from the `mock_cmssw_categories` autouse fixture):

| Category | Package prefixes |
|---|---|
| `core` | `Package/Core`, `Package/Framework` |
| `analysis` | `Package/Analysis` |
| `simulation` | `Package/Simulation` |
| `docs` | `Package/Docs` |
| `testing` | `Package/Testing` |
| `reconstruction` | `Package/Reconstruction` |
| *(others)* | see `mock_cmssw_categories` fixture in test file |

#### `comments: List[Dict] = None`
Issue comments on the PR, including bot commands and the bot's own cache comment.
Each dict supports these fields:

```python
comments=[
    {
        "id": 100,                            # required — unique int, used as comment ID
        "body": "+1",                         # required — comment text / command
        "user": {"login": "alice", "id": 2},  # required unless `user=` param is set
        "created_at": "2025-12-12T12:00:00Z", # optional — defaults to FROZEN_COMMENT_TIME
    }
]
```

- `id` must be unique across all comments in the same test.
- `created_at` is optional — defaults to `FROZEN_COMMENT_TIME` (`2025-12-12T12:00:00Z`).
- `user` can be omitted if a default `user=` is provided to `create_basic_pr_data`
  (see [User fixtures](#user-fixtures) below).

**Default** (when `None`): no comments.

#### `commits: List[Dict] = None`
Commits on the PR branch. The last commit's `sha` is used as `pr.head.sha`.

```python
commits=[
    {
        "sha": "commit_abc123",
        "commit": {
            "message": "Fix the bug",
            "author": {
                "date": "2025-12-12T11:00:00Z",
                "name": "Developer",
                "email": "dev@example.com",
            },
            "committer": {
                "date": "2025-12-12T11:00:00Z",
                "name": "Developer",
                "email": "dev@example.com",
            },
        },
    }
]
```

**Default** (when `None`): a single commit with sha `commit123` at `FROZEN_COMMIT_TIME`
(one hour before `FROZEN_COMMENT_TIME`). Signatures made after `FROZEN_COMMIT_TIME` are
valid; signatures before it are ignored.

#### `labels: List[str] = None`
Labels already present on the PR at the start of processing.

```python
labels=["pending-signatures", "core-pending"]
```

**Default** (when `None`): no labels.

#### `base_ref: str = "main"`
The target branch of the PR (`pr.base.ref`). Use `"master"` for cms-sw/cmssw tests
that require master-branch behaviour.

```python
base_ref="master"   # triggers CMSSW-specific signing rules
```

#### `statuses: List[Dict] = None`
GitHub commit statuses on the head commit. Used to test CI status handling.

```python
statuses=[
    {
        "context": "cms/1/el8_amd64_gcc13/required",
        "state": "success",
        "description": "All tests passed",
        "target_url": "https://jenkins.example.com/job/123",
    },
    {
        "context": "cms/1/code-checks",
        "state": "pending",
        "description": "Running",
        "target_url": "",
    },
]
```

**Default** (when `None`): no commit statuses.

#### `login: str = "testuser"`
GitHub login of the PR author (sets `pr.user.login` and `issue.user.login`).
Change when the test depends on who opened the PR.

```python
login="alice"   # PR was opened by alice
```

#### `user: Dict[str, Any] = None`
Default user dict applied to every comment that does not already have a `"user"` key.
Pass a user fixture here to avoid repeating the user dict in every comment.
See [User fixtures](#user-fixtures) below.

```python
create_basic_pr_data(
    test_name,
    comments=[
        {"id": 100, "body": "+1"},    # gets alice_user automatically
        {"id": 101, "body": "hold"},  # gets alice_user automatically
    ],
    user=alice_user,
)
```

---

## User Fixtures

User fixtures are `pytest` fixtures that return a `{"login": ..., "id": ...}` dict
matching the L2 membership pre-configured by the `setup_l2_data` autouse fixture.
**Always use these instead of writing inline dicts** — they keep usernames consistent
with `_L2_DATA` so re-recording is never needed just because of a refactor.

### Available fixtures

| Fixture | `login` | L2 categories |
|---|---|---|
| `alice_user` | `alice` | `core`, `analysis` |
| `bob_user` | `bob` | `simulation` |
| `carol_user` | `carol` | `docs`, `testing` |
| `dave_user` | `dave` | `orp` |
| `cmsbuild_user_dict` | `cmsbuild` | `tests`, `code-checks` (bot) |
| `tester_user` | `tester` | none — add to `TRIGGER_PR_TESTS` in test |
| `testuser` | `testuser` | none — default PR author |

Declare them in the test signature the same way as `repo_config` or `record_mode`:

```python
def test_something(self, test_name, alice_user, bob_user, repo_config, record_mode):
```

### Single user for all comments

Pass the fixture as `user=` to `create_basic_pr_data`. Every comment that lacks an
explicit `"user"` key will inherit it:

```python
def test_approval(self, test_name, alice_user, repo_config, record_mode):
    create_basic_pr_data(
        test_name,
        comments=[
            {"id": 100, "body": "+1"},     # alice_user applied automatically
            {"id": 101, "body": "hold"},   # alice_user applied automatically
        ],
        user=alice_user,
    )
```

### Multiple users in one test

Specify `"user"` explicitly on comments that need a different user. Comments without
`"user"` still fall back to the `user=` default (if given):

```python
def test_multi_user(self, test_name, alice_user, bob_user, repo_config, record_mode):
    create_basic_pr_data(
        test_name,
        files=[
            {"filename": "Package/Core/f.cc",       "sha": "sha1", "status": "modified"},
            {"filename": "Package/Simulation/f.cc",  "sha": "sha2", "status": "modified"},
        ],
        comments=[
            {"id": 100, "body": "+core",       "user": alice_user},  # alice signs core
            {"id": 101, "body": "+simulation", "user": bob_user},    # bob signs simulation
        ],
        # no `user=` — every comment has its own explicit user
    )
```

### Adding a new user fixture

Add the fixture near the others in the test file and add the user to
`setup_test_l2_data`'s default dict:

```python
# In test file:
@pytest.fixture
def eve_user():
    """L2 user with 'tracking' category."""
    return {"login": "eve", "id": 7}
```

```python
# In setup_test_l2_data():
user_categories = {
    ...
    "eve": ["tracking"],
}
```

---

## Autouse Fixtures (Applied to Every Test Automatically)

These run before/after every test without being declared in the test signature:

| Fixture | What it does |
|---|---|
| `setup_l2_data` | Populates `_L2_DATA` with alice/bob/carol/dave/cmsbuild; resets to `{}` after |
| `mock_cmssw_categories` | Replaces `CMSSW_CATEGORIES` with a deterministic test mapping |
| `clear_mock_commit_statuses` | Clears `MockCommit._shared_statuses` between tests |
| `freeze_time` | Patches `datetime.now()` to always return `FROZEN_TIME` |

Frozen time constants:

| Constant | Value | Role |
|---|---|---|
| `FROZEN_TIME` | `2025-12-12T12:00:00Z` | What `datetime.now()` returns |
| `FROZEN_COMMIT_TIME` | `2025-12-12T11:00:00Z` | Default commit timestamp (1 h before) |
| `FROZEN_COMMENT_TIME` | `2025-12-12T12:00:00Z` | Default comment timestamp |

Signatures posted at `FROZEN_COMMENT_TIME` are after `FROZEN_COMMIT_TIME`, so they
are valid for the default commit.

---

## Overriding L2 Data in a Single Test

When a test requires non-default L2 membership (e.g. time-bounded changes), call
`setup_test_l2_data()` directly inside the test before calling `process_pr`:

```python
def test_membership_change(self, test_name, repo_config, record_mode):
    t_change = FROZEN_COMMIT_TIME + timedelta(minutes=10)
    setup_test_l2_data({
        "alice": [
            {"start_date": 0,                     "end_date": t_change.timestamp(), "category": ["core"]},
            {"start_date": t_change.timestamp(),  "end_date": None,                 "category": ["dqm"]},
        ],
        "cmsbuild": [{"start_date": 0, "category": ["tests", "code-checks"]}],
    })
    ...
```

`setup_l2_data` (autouse) still resets `_L2_DATA = {}` after the test.

---

## Testing Multi-Run Scenarios (Cache Preservation)

Some tests simulate two consecutive bot runs on the same PR (e.g. a file being reverted
after signatures were already given). The cache is stored as special bot comments on the
issue, so it must be preserved across calls.

Pattern: after the first run, read all current comments back via `issue.get_comments()`
and pass them to the second `create_basic_pr_data` call alongside the updated state.
Then recreate the mock objects to pick up the new fixture files.

```python
# First run
create_basic_pr_data(test_name, files=[file_a, file_b], comments=[...])
issue = MockIssue(test_name, number=1, recorder=recorder)
result1 = process_pr(...)

# Preserve cache: collect all comments the bot wrote (including the cache comment)
all_comments = [
    {
        "id": c.id,
        "body": c.body,
        "user": {"login": c.user.login, "id": c.user.id},
        "created_at": c.created_at,
    }
    for c in issue.get_comments()
]

# Second run: file_b reverted, cache preserved via all_comments
create_basic_pr_data(test_name, files=[file_a], comments=all_comments)
issue2 = MockIssue(test_name, number=1, recorder=recorder)  # recreate to reload files
result2 = process_pr(repo_config=repo_config, gh=gh2, repo=repo2, issue=issue2, ...)
```

**Why recreate mock objects?** `MockIssue` caches its fixture data at construction time.
Recreating forces a re-read of the updated JSON on disk.

**Why reuse the same `recorder`?** It accumulates actions across both runs, so a single
`recorder.save()` / `recorder.verify()` at the end covers the full scenario.

---

## Checking Results

`process_pr` returns a dict:

| Key | Type | Description |
|---|---|---|
| `pr_number` | `int` | PR number |
| `pr_state` | `str` | `"signatures-pending"`, `"fully-signed"`, `"merged"`, … |
| `categories` | `Dict[str, Dict]` | Per-category state |
| `labels` | `Set[str]` | Final label set after processing |

Each `categories` entry:
```python
result["categories"]["core"] == {
    "state": "approved",      # "pending", "approved", or "rejected"
    "check_type": "regular",  # "regular", "pre_check", or "extra_check"
}
```

Common assertions:
```python
assert result["categories"]["core"]["state"] == "approved"
assert "core-approved" in result["labels"]
assert "simulation-pending" not in result["labels"]   # category was removed
```

---

## Simple Unit Tests

For testing pure functions that don't need the full `process_pr` flow, use `MagicMock`
directly — no fixture files needed:

```python
def test_parse_something(self):
    context = MagicMock(spec=PRContext)
    context.pr = MagicMock()
    context.pr.draft = False

    result = my_function(context)
    assert result == expected
```
