# CMS-Bot Process PR V2 - Design Document

## Overview

`process_pr_v2.py` is a comprehensive GitHub bot for automating CI tests and PR reviews
for the CMS-SW project. The bot is designed to be **stateless**, storing all necessary
state in PR/Issue comments as a compressed cache.

## Architecture

### Core Design Principles

1. **Stateless Operation**: The bot reconstructs state from GitHub comments on each invocation
2. **Decorator-Based Commands**: Commands are registered via `@command` decorators for clean separation
3. **Snapshot-Based Tracking**: File states and signatures are tracked via snapshots keyed to blob SHAs
4. **Chronological Processing**: Comments are processed in timestamp order to build accurate state
5. **Deferred Actions**: Labels, statuses, and comments are queued during processing and applied at the end

### Key Data Structures

#### PRContext

Central context object holding all state during PR/Issue processing:

- Repository and PR/Issue references (`repo`, `pr`, `issue`, `commits`)
- Cache (`cache: BotCache`) — signatures, file states, processed comments
- `signing_categories`: Set of categories requiring L2 signatures
- `granted_test_rights`: Set of users granted test rights via `allow @user test rights`
- `pending_labels` / `pending_labels_to_remove`: Label changes to apply
- `pending_status_updates`: Dict mapping `context_name → (sha, state, desc, url)` for deferred status updates
- `pending_build_test_command`: Single pending build/test command (last one wins)
- `holds`: Dict of active holds preventing merge
- `_last_commit`: Cached last commit (by committer date)
- `_commit_statuses`: Frozen cache of commit statuses at start of processing
- `notify_without_at`: If True, mentions use plain username instead of `@username`

#### BotCache

Compressed cache stored in a special bot comment:

- `emoji`: Dict mapping `comment_id → reaction` (bot's reactions — source of truth)
- `file_versions`: Dict mapping `"filename::sha" → FileVersion` (categories, timestamp)
- `comments`: Dict of `comment_id → CommentInfo` (processed comment metadata)
- `current_file_versions`: List of current `"filename::sha"` keys — **not persisted**,
  rebuilt from `pr.get_files()` on every run by `update_file_states()`

#### FileVersion

Tracks file state at a specific blob SHA:

- `filename`: File path
- `blob_sha`: Git blob SHA
- `timestamp`: When this version was first seen
- `categories`: L2 categories this file belongs to (from `CMSSW_CATEGORIES`)

**Reverted files**: If a file no longer appears in `pr.get_files()` (reverted to base),
its `FileVersion` entry is removed from the cache so its categories are no longer
required for signatures.

#### CommentInfo

Cached comment metadata:

- `timestamp`: Comment creation time (ISO string)
- `first_line`: First non-blank line of the comment body
- `ctype`: Command type (`"+1"`, `"-1"`, `"hold"`, etc.)
- `categories`: Categories this signature applies to
- `signed_files`: List of `"filename::sha"` strings that were signed
- `user`: Comment author login
- `locked`: If True, comment won't be reprocessed (e.g., outdated signature before a commit)

#### CommandUser

Helper object wrapping a commenter for ACL checks:

| Property | Description |
|---|---|
| `login` | GitHub username |
| `user_categories` | L2 categories at comment time |
| `is_valid_commenter` | L2, release manager, or granted test rights |
| `is_release_manager` | In current release manager list |
| `is_pr_hold_manager` | In `PR_HOLD_MANAGERS` config |
| `is_orp` | In ORP (operations) role |
| `is_requestor` | Is the PR author |
| `is_cmsbuild_user` | Is the bot |
| `is_issue_tracker` | In `CMSSW_ISSUES_TRACKERS` config |

## Command System

### Command Registration

Commands are registered using the `@command` decorator:

```python
@command("name", r"^regex_pattern$", description="...", pr_only=True,
         acl=lambda u: bool(u.user_categories))
def handle_name(context: PRContext, match: re.Match, comment: Any) -> Optional[bool]:
    ...
```

Handler signature is `(context, match, comment)` — the full comment object is passed,
not separate `user`/`comment_id`/`timestamp` parameters.

Return values: `True` = success (`:+1:`), `False` = failure (`:-1:`), `None` = fallthrough.

### Implemented Commands

#### Approval Commands
| Command | Description | ACL |
|---|---|---|
| `+1` | Approve all user's L2 categories | Any L2 |
| `-1` | Reject all user's L2 categories | Any L2 |
| `+<category>` | Approve specific category | L2 member of that category; bot for pre-checks |
| `-<category>` | Reject specific category | L2 member of that category; bot for pre-checks |

Signing for a category you don't belong to returns `False` (`:−1:` reaction).
Pre-check categories (e.g. `code-checks`) can only be signed by the bot user.

#### Category Management
| Command | Description | ACL |
|---|---|---|
| `assign <cat\|pkg>` | Add categories to PR (by category name or package path) | Any L2 or issue tracker |
| `unassign <cat\|pkg>` | Remove categories from PR | Any L2 or issue tracker |

#### Hold Commands
| Command | Description | ACL |
|---|---|---|
| `hold` | Prevent automerge | L2, release manager, or `PR_HOLD_MANAGERS` |
| `unhold` | Remove hold | ORP removes all holds; others remove only their own |

#### Test Commands
| Command | Description | ACL |
|---|---|---|
| `test [params]` | Trigger CI tests | Valid testers |
| `build [params]` | Trigger build only | Valid testers |
| `test parameters:` | Set test parameters (multi-line) | Valid testers |
| `enable <tests>` | Enable specific bot tests | Valid testers |
| `abort` / `abort test` | Abort running tests | Valid testers |
| `code-checks [params]` | Run code quality checks | Valid testers |

"Valid testers" = users in `TRIGGER_PR_TESTS`, any L2, release managers, or users
granted test rights via `allow @user test rights`.

#### Access Control Commands
| Command | Description | ACL |
|---|---|---|
| `allow @<user> test rights` | Grant test rights to a user; adds `allow-<user>` label | L2 or release manager |
| `ignore tests-rejected with <reason>` | Override test rejection | Any (reset on push) |
| `+file-count` | Override "too many files" warning | `CMSSW_ISSUES_TRACKERS` |

#### Label Commands
| Command | Description | ACL |
|---|---|---|
| `type <labels>` | Add/remove labels (with `+`/`-` prefix); one `type`-group label at a time | L2, release manager, or PR author |
| `backport <release>` | Mark PR as backport | L2 |
| `urgent` | Mark as urgent | L2 |

#### PR Lifecycle Commands
| Command | Description | ACL |
|---|---|---|
| `merge` | Request merge | Release manager or ORP |
| `close` | Close PR/Issue | L2, release manager, or issue tracker |
| `reopen` | Reopen PR/Issue | L2, release manager, or issue tracker |

## Signature System

### Signature Flow

1. **File Detection**: Changed files fetched from `pr.get_files()`
2. **Category Assignment**: Files mapped to categories via `CMSSW_CATEGORIES`
3. **L2 Assignment**: Each category has L2 signers from `_L2_DATA` (loaded by `init_l2_data()`)
4. **Signature Collection**: L2 members approve/reject via `+1`/`-1`/`+cat`/`-cat`
5. **File Tracking**: Each signature records the blob SHAs for signed categories

### L2 Data Loading

L2 category membership is loaded once per run by `init_l2_data(repo_config, cms_repo)`,
called at the start of `process_pr()`. It reads from repo-specific `l2.json` (falling back
to the default `cmssw_l2/l2.json`). The function is a no-op if `_L2_DATA` is already
populated (tests pre-populate it via the `setup_l2_data` autouse fixture).

### Signature Validation

A signature for a category is valid only if:
1. **Files unchanged**: All signed `filename::sha` pairs still match current file versions
2. **No new files**: No new files have been added to the category since signing

Example:
1. Category `core` has files `[A::sha1, B::sha2]`
2. User signs `core` → records `signed_files: ["A::sha1", "B::sha2"]`
3. Signature becomes **invalid** if A changes to `A::sha3`, or new file C is added to `core`
4. Signature remains **valid** if a file in a different category changes, or the user's L2 membership changes

### Reverted Files

If a file is reverted to base, it disappears from `pr.get_files()`. On the next bot run:
- Its `FileVersion` entry is removed from `cache.file_versions`
- Its categories are removed from `current_file_versions`
- Any category no longer covered by remaining files is removed from the required set
- Stale category labels (`<cat>-pending`, `<cat>-approved`, etc.) are removed by `update_pr_status()`
- The PR updated message notes the removed categories

### Pre-Checks and Extra-Checks

- **PRE_CHECKS** (e.g., `code-checks`): must be approved before tests can run; signed
  exclusively by the bot. Approval/rejection updates a GitHub commit status:
  `cms/{prId}/{precheck}` → `success` / `error`.
- **EXTRA_CHECKS** (e.g., `orp`): additional categories required for merge.

## Build/Test Command Processing

### Deferred Processing

Build and test commands are stored as a single slot after comment processing:

```
context.pending_build_test_command = (comment, result)
```

Only the last command matters — build and test write to the same properties file.
Actual execution happens in `process_pending_build_test_commands()` after all comments.

### Deduplication

- **Build**: skipped if the comment already has a bot `+1` reaction
- **Test**: skipped if `bot/{prId}/jenkins` status URL matches the comment URL

### Jenkins Status Tracking

After triggering tests, the bot sets:
- Context: `bot/{prId}/jenkins`
- State: `success`
- Description: `Tests requested by {user} at {time} UTC.`
- URL: Comment URL that triggered the test

After abort:
- State: `pending`
- Description: `Aborted, waiting for authorized user to issue the test command.`

### Tests Approval State

The `tests` category state is determined by `_get_tests_approval_state()`:

| State | Condition |
|---|---|
| `PENDING` | No results; jenkins status has no "requested by" |
| `STARTED` | No results; jenkins status contains "requested by" |
| `APPROVED` | Required tests passed |
| `REJECTED` | Required tests failed (unless `ignore_tests_rejected` is set) |

## Commit Status System

### Frozen Cache

Commit statuses are fetched once at the start and cached:

```python
statuses = context.get_commit_statuses()          # Dict[name, status]
status  = context.get_commit_status("cms/1/...")  # Single status or None
```

The cache is never updated during a run. Status changes take effect on the next bot invocation.

### Deferred Updates

All status updates are queued during processing and written together at the end:

1. `context.queue_status_update(state, description, context_name, target_url)`
2. Stored in `pending_status_updates` dict — last update per context wins
3. Applied by `flush_pending_statuses()` at end of `process_pr()`
4. Only statuses that actually changed are written (compared against frozen cache)

Some functions check `pending_status_updates` first to see changes from the current run
(e.g., `_get_tests_approval_state()` after an abort command).

## Label Management

### Category State Labels

`update_pr_status()` maintains `<cat>-pending`, `<cat>-approved`, `<cat>-rejected`,
and `<cat>-started` labels for each required category.

When a category is removed (e.g., because its file was reverted to base), all its state
labels are removed automatically: the function scans existing labels for any that end with
a state suffix but whose category is no longer in `current_categories`.

### Overall State Labels

| Label | Condition |
|---|---|
| `pending-signatures` | Any category pending or rejected |
| `fully-signed` | All categories approved |
| `fully-signed-draft` | All categories approved, but PR is a draft |
| `merged` | PR is merged |

## Bot Messages

### Welcome Message

Posted when a new PR is created (skipped for draft PRs). Includes:
- Author mention
- Assigned categories and L2 signers
- Commands reference
- Unknown category warnings

Draft PRs: welcome is delayed until the PR leaves draft state.

### PR Updated Message

Posted when new commits are pushed:

```
Pull request #{n} was updated. {signers} can you please check and sign again.

The following packages are now also affected:
- Package/Foo (**category**)

{new-L2s} can you please review and sign?

The following categories are no longer affected: **old-cat**
```

- New categories (files added touching new packages) are listed with their L2s.
- Removed categories (files reverted to base) are listed as no longer affected.
- Skipped for draft PRs.

### Fully-Signed Message

Posted when the `fully-signed` label is first applied.

## Cache Storage

Cache is stored in a bot comment with this format:
```
cms-bot internal usage<!-- {compressed_data} -->
```

### Compression

1. JSON serialization with compact separators
2. gzip compression if > chunk size threshold
3. base64 encoding
4. Split into multiple comments if still too large

### Cache Keys

Cache keys are always **strings**, while GitHub object IDs are integers. Convert when needed:

```python
context.cache.comments[str(comment_id)]   # keyed by string
context.cache.emoji[str(comment_id)]      # keyed by string
comment.id                                # int from GitHub API
```

## Ignore Logic

PRs/Issues are skipped if:
1. Issue number in `repo_config.IGNORE_ISSUES`
2. Title matches `^[Bb]uild[ ]+(CMSSW_[^ ]+)` (release builds)
3. First line contains `<cms-bot></cms-bot>` tag

## Repository Classification

| Flag | Condition |
|---|---|
| `cmssw_repo` | `repo_name == GH_CMSSW_REPO` |
| `cms_repo` | `repo_org in EXTERNAL_REPOS` |
| `external_repo` | `repo_name != CMSSW_REPO_NAME and repo_org in EXTERNAL_REPOS` |

For external repos, an `externals` category is added to `signing_categories`.
CMSDIST repos validate the branch against `VALID_CMSDIST_BRANCHES`.

## Draft PR Handling

- `@` mentions replaced with plain usernames (no notifications)
- Welcome message delayed until PR exits draft state
- Re-sign notifications skipped on commit updates
- Can be overridden with `<notify></notify>` tag in PR body

## Configuration (`repo_config.py`)

| Variable | Description |
|---|---|
| `CMSSW_CATEGORIES` | File-path prefix → category mapping |
| `CMSSW_L2` | Category → list of L2 signers (static fallback) |
| `CMSSW_LABELS` | File-path prefix → label mapping |
| `CMSSW_ISSUES_TRACKERS` | Issue tracker usernames |
| `PR_HOLD_MANAGERS` | Users who can place holds |
| `TRIGGER_PR_TESTS` | Users who can trigger tests |
| `PRE_CHECKS` | Categories required before tests |
| `EXTRA_CHECKS` | Categories required for merge |
| `IGNORE_ISSUES` | Issue numbers to skip |

## Thresholds

| Threshold | Value | Effect |
|---|---|---|
| `TOO_MANY_COMMITS_WARN_THRESHOLD` | 150 | Warning comment |
| `TOO_MANY_COMMITS_FAIL_THRESHOLD` | 240 | Block processing |
| `TOO_MANY_FILES_WARN_THRESHOLD` | 1500 | Warning comment (CMSSW only) |
| `TOO_MANY_FILES_FAIL_THRESHOLD` | 3001 | Block processing (CMSSW only) |

## Dry-Run Mode

When `dryRun=True`, all processing logic runs but mutating API calls are skipped:
`create_comment`, `edit`, `add_to_labels`, `remove_from_labels`, `create_status`,
`comment.edit`, `comment.delete`, property file creation.

## Error Handling

- Graceful degradation on missing/malformed data
- Detailed logging at DEBUG/INFO/WARNING/ERROR levels
- `get_commit_statuses()` catches `AttributeError`, `TypeError`/`ValueError`, and
  unexpected exceptions separately, logging at appropriate levels and returning `{}`

## File Structure

```
process_pr_v2.py          # Main implementation (~7450 lines)
test_process_pr_v2.py     # Test suite (~10000 lines)
conftest.py               # Pytest configuration (record_mode fixture)
ReplayData/               # Fixture JSON files (one dir per test)
PRActionData/             # Recorded action JSON files (one dir per test)
DESIGN.md                 # This design document
COMMANDS.md               # Command implementation guide
TESTING.md                # Test writing guide
```

## Dependencies

### External
- `PyGithub`: GitHub API access
- `yaml`: Configuration parsing
- `gzip`, `base64`: Cache compression

### CMS-SW Modules
- `categories`: `CMSSW_L2`, `CMSSW_CATEGORIES`, etc.
- `cms_static`: Constants (`BUILD_REL`, etc.)
- `releases`: Release manager lookup
- `_py2with3compatibility`: `run_cmd`
