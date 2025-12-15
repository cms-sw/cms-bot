# CMS-Bot Process PR V2 - Design Document

## Overview

`process_pr_v2.py` is a comprehensive GitHub bot for automating CI tests and PR reviews for the CMS-SW project. The bot is designed to be **stateless**, storing all necessary state in PR/Issue comments as a compressed cache.

## Architecture

### Core Design Principles

1. **Stateless Operation**: The bot reconstructs state from GitHub comments on each invocation
2. **Decorator-Based Commands**: Commands are registered via `@command` decorators for clean separation
3. **Snapshot-Based Tracking**: File states and signatures are tracked via snapshots keyed to commit SHAs
4. **Chronological Processing**: Comments are processed in timestamp order to build accurate state
5. **Deferred Command Processing**: Build/test commands are collected and deduplicated before execution

### Key Data Structures

#### PRContext
Central context object holding all state during PR/Issue processing:
- Repository and PR/Issue references
- Cache (signatures, file states, test requests)
- Signing categories and holds
- Pending labels and test triggers
- Configuration flags (dry_run, force, etc.)
- Package categories mapping
- `commits`: Dict mapping SHA → commit object (for O(1) lookup)
- `_last_commit`: Cached last commit (by committer date)
- `_commit_statuses`: Cache mapping SHA → list of statuses
- `pending_status_updates`: Queue of status updates to flush at end
- `pending_bot_comments`: Queue of comments to post at end

#### BotCache
Compressed cache stored in issue comments:
- `emoji`: Dict mapping comment_id to bot's reaction (source of truth for reactions)
- `fv` (file_versions): Dict mapping `"filename::sha"` to `{ts, cats}` 
- `comments`: Dict of processed `CommentInfo` objects with timestamps, first_line, ctype, categories, signed_files, user, locked

#### FileVersion
Tracks file state:
- `filename`: File path
- `blob_sha`: Git blob SHA
- `timestamp`: When this version was seen
- `categories`: Categories this file belongs to

#### CommentInfo
Cached comment data:
- `timestamp`: Comment creation time
- `first_line`: First non-blank line (for command detection)
- `ctype`: Comment type (e.g., "sign", "hold")
- `categories`: Categories affected
- `signed_files`: List of `"filename::sha"` strings signed
- `user`: Comment author
- `locked`: Whether comment is locked (won't be reprocessed)

## Command System

### Command Registration

Commands are registered using the `@command` decorator:

```python
@command("name", r"^regex_pattern$", description="...", pr_only=True)
def handle_name(context, match, user, comment_id, timestamp):
    ...
```

### Implemented Commands

#### Approval Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `+1` | `^\+1$` | Approve category/categories | L2 signers for category |
| `-1` | `^-1$` | Reject category/categories | L2 signers for category |
| `+category` | `^\+([\w-]+)$` | Approve specific category | L2 signers for that category |
| `-category` | `^-([\w-]+)$` | Reject specific category | L2 signers for that category |

#### Category Management
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `assign <cats>` | `^assign\s+(.+)$` | Add categories to PR | L2 signers |
| `unassign <cats>` | `^unassign\s+(.+)$` | Remove categories from PR | L2 signers |

#### Hold Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `hold` | `^hold$` | Place hold to prevent automerge | L2 signers, Release Managers, PR_HOLD_MANAGERS |
| `unhold` | `^unhold$` | Remove hold | ORP (all holds), Others (own holds only) |

#### Test Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `test [params]` | `^test(\s+.*)?$` | Trigger CI tests | Valid testers (TRIGGER_PR_TESTS, L2s, Release Managers) |
| `build [params]` | `^build(\s+.*)?$` | Trigger build only | Valid testers |
| `test parameters <params>` | `^test\s+parameters\s+(.+)$` | Set test parameters | Valid testers |
| `abort` | `^abort$` | Abort running tests | Valid testers |
| `abort test` | `^abort\s+test$` | Abort running tests | Valid testers |

#### Code Quality Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `code-checks` | `^code-checks(\s+.*)?$` | Run code quality checks | Valid testers |

#### Label Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `type <label>` | `^type\s+(\S+)$` | Set PR type label (replaces previous) | Anyone |
| `mtype <labels>` | `^mtype\s+(.+)$` | Add multiple type labels (accumulates) | Anyone |
| `urgent` | `^urgent$` | Mark as urgent | L2 signers |
| `backport <release>` | `^backport\s+(.+)$` | Mark PR as backport to release | L2 signers |

#### PR Lifecycle Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `merge` | `^merge$` | Request merge | Anyone (if merge conditions met) |
| `close` | `^close$` | Close PR/Issue | L2 signers, Release Managers, Issue Trackers |
| `reopen` | `^reopen$` | Reopen PR/Issue | L2 signers, Release Managers, Issue Trackers |

#### Access Control Commands
| Command | Pattern | Description | Permissions |
|---------|---------|-------------|-------------|
| `allow test rights` | `^allow\s+test\s+rights$` | Grant test rights to author | L2 signers |
| `ignore tests-rejected` | `^ignore\s+tests-rejected(\s+.*)?$` | Override test rejection | L2 signers |

## Signature System

### Signature Flow

1. **File Detection**: When a PR is opened/updated, changed files are detected via `pr.get_files()`
2. **Category Assignment**: Files are mapped to categories via `categories_map.py`
3. **L2 Assignment**: Each category has L2 signers from `CMSSW_L2` configuration
4. **Signature Collection**: L2 signers approve/reject their categories
5. **File Tracking**: Each signature records the blob SHAs for files in signed categories

### File Version Tracking

Files are tracked using blob SHAs from the GitHub API:
- Key format: `"filename::blob_sha"` (e.g., `"src/core/main.py::a1b2c3d4"`)
- Blob SHA uniquely identifies file content (same content = same SHA across commits)
- File versions are fetched from `pr.get_files()` which provides real blob SHAs

### Signature Validation

A signature for a category is valid only if:
1. **No files changed**: All files that were signed still have the same blob SHA
2. **No files added**: All current files in the category were covered by the signature

Example:
1. Category "core" has files [A::sha1, B::sha2]
2. User signs category "core" → records `signed_files: ["A::sha1", "B::sha2"]`
3. Signature becomes **invalid** if:
   - File A changes to A::sha3 (file content changed, different blob SHA)
   - File C::sha1 is added to category "core" (new file not signed)
4. Signature remains **valid** if:
   - File D is added to a different category
   - User's L2 membership changes
   - A new commit is pushed that doesn't change file content (same blob SHAs)

### Design Decisions

**Blob SHA vs Commit SHA:** Using blob SHAs instead of commit SHAs allows signatures to remain valid when commits are rebased or amended without changing file content. This avoids unnecessary re-signing.

**File Reverts:** If a file is reverted to a previously-signed content, the old signature is NOT automatically restored. We only track the current file versions - any change invalidates signatures for that file's categories, even if reverting to previously-signed content. L2 must re-sign.

**Category Mapping Changes:** When a file is modified, its category mapping is recalculated using current rules. The mapping is only frozen while the file content remains unchanged.

### Valid Signing Categories

When processing `+category` or `-category` commands, the category must be a valid signing category:
1. L2 categories from file ownership (in `context.signing_categories`)
2. Manually assigned categories via `assign` command (in `context.signing_categories`)
3. Pre-checks (e.g., `code-checks`) from `signing_checks.pre_checks`
4. Extra-checks (e.g., `orp`, `tests`, `externals`) from `signing_checks.extra_checks`

### Pre-Checks and Extra-Checks

- **PRE_CHECKS**: Categories that must be approved before tests can run (e.g., `code-checks`)
- **EXTRA_CHECKS**: Additional categories for special handling (e.g., `orp`, `tests`, `externals`)

**Important:** `fully-signed` status only waits for L2 category signatures (from file ownership and manual assignment). It does NOT wait for:
- `code-checks` (pre-check)
- `tests` (extra-check)
- `orp` (extra-check)

These are checked separately:
- `code-checks`: Required before tests can be triggered
- `tests` + `orp`: Required for merge (checked in `can_merge()`)

#### Pre-Check Status Tracking

Pre-checks use commit statuses as the source of truth (NOT cached signatures):

| State | Description | Trigger |
|-------|-------------|---------|
| `pending` | `{precheck} pending` | New commit pushed (reset) or auto-triggered |
| `success` | `See details` | Signed with `+code-checks` |
| `error` | `See details` | Signed with `-code-checks` |

**On new commit**: Pre-check statuses are reset to "pending" via `reset_pre_check_statuses()`.

**On sign**: The `+/-code-checks` comment is posted AND the commit status is updated directly. Pre-check signatures are NOT stored in the cache - only regular L2 signatures are cached.

**Auto-triggering**: When tests are triggered (`create_test_property=True`), pre-checks without existing status are automatically triggered via `trigger_pending_pre_checks()`.

### New Package Detection

For CMSSW repos, packages without category assignments trigger the `new-package` signing category:
- Detected by comparing packages against `CMSSW_CATEGORIES.values()`
- Adds `new-package` to `context.signing_categories`
- Blocks `fully-signed` until signed
- Blocks merge until signed

## Build/Test Command Processing

### Deferred Processing

Build and test commands are collected during comment processing and executed after all comments have been seen. This enables deduplication and "last one wins" semantics.

### Deduplication Rules

**Build commands**: Skip if comment already has `+1` reaction from the bot (cmsbuild_user). Each build command is processed individually.

**Test commands**: "Last one wins" - only the most recent test command is processed. Skip if:
- A `bot/{prId}/jenkins` commit status exists AND
- The status URL matches the comment URL (same test already triggered)

### Jenkins Status Tracking

After successfully triggering a test command, the bot sets a commit status:
- Context: `bot/{prId}/jenkins`
- State: `pending`
- Description: "Tests requested by {user} at {timestamp}"
- Target URL: Comment URL that triggered the test

This allows detecting if a test command was already processed.

### Commit Status Caching

The bot caches commit statuses to avoid repeated API calls:
- `PRContext.get_commit_statuses(sha)`: Fetches and caches statuses for a commit
- Cache is invalidated when statuses are updated via `flush_pending_statuses()`

### Deferred Status Updates

All commit status updates are queued during processing and executed at the end:
1. Functions call `context.queue_status_update(state, description, context_name, target_url, sha)`
2. At end of `process_pr()`, `flush_pending_statuses()` executes all queued updates
3. This prevents cache invalidation during processing and ensures consistent state

### create_test_property Flag

Controls whether `.properties` files are created for build/test/abort commands:
- `True` if `cmssw_repo or not external_repo`
- `True` for external repos if `(repo_org != GH_CMSSW_ORGANIZATION) or (repo_name in VALID_CMS_SW_REPOS_FOR_TESTS)`
- `False` if PR is closed

## Bot Mention Detection

### @-mention Handling

When a comment mentions the bot (e.g., `@cmsbuild`), the bot tracks this and:
- If the command is recognized and authorized: normal processing
- If the command is NOT recognized: sets `-1` reaction on the comment
- ACL failures always get `-1` reaction
- Command execution failures get `-1` reaction

The bot username is configurable via `cmsbuild_user` parameter.

## Ignore Logic

Issues/PRs can be ignored based on:

1. **IGNORE_ISSUES Config**: Issue number in `repo_config.IGNORE_ISSUES`
2. **Repo-Specific Ignore**: Issue number in `IGNORE_ISSUES[repo.full_name]`
3. **BUILD_REL Pattern**: Title matches `^[Bb]uild[ ]+(CMSSW_[^ ]+)` (release builds)
4. **CMSBOT_IGNORE_MSG**: First line contains `<cms-bot></cms-bot>` tag

## Test System

### Test Command Parsing

Test commands support various parameters:
- `workflows <ids>`: Specific workflow IDs to run
- `pull_requests <prs>`: Additional PRs to include
- `full_cmssw`: Use full CMSSW checkout
- `using addpkg <pkg>`: Add specific packages
- `queue <n>`: Target specific queue

### Test Deduplication

Test requests are deduplicated based on:
- Command verb (test/build)
- Workflow IDs (order-independent)
- Other parameters

### CI Test Status Detection

The bot monitors GitHub commit statuses:
- Pattern: `cms/{prId}/<arch>/<test_type>/required` or `/optional`
- Tracks sub-statuses for build, relvals, etc.
- Posts results as +1/-1 comments when complete

### CI Result Message Keys

CI result comments use a unique message key to prevent duplicate posting:
- Key format: `ci_result_{status_context}_{url_hash}`
- `url_hash` is the hash of the Jenkins build URL (unique per test run)
- This allows re-triggering tests on the same commit to post new results
- The "Finished" description check prevents duplicate processing within the same test run

### Test Rejection Override

The `ignore tests-rejected with <reason>` command allows overriding test failures:
- Only takes effect if tests are actually in rejected state (CI status is "error")
- Changes `tests` signature to `approved`
- Adds `tests-{reason}` label to indicate override
- Fully-signed message shows "(test failures were overridden)"
- Valid reasons are defined in `githublabels.TEST_IGNORE_REASON`

## Cache System

### Cache Storage

Cache is stored in special bot comment(s):
```
cms-bot internal usage<!-- {data} -->
```

### Compression Strategy

Cache compression is applied conditionally based on size:

1. **Small cache (≤ BOT_CACHE_CHUNK_SIZE)**: Stored as plain JSON without compression
2. **Large cache (> BOT_CACHE_CHUNK_SIZE)**: Compressed and potentially split across multiple comments

Compression pipeline (when needed):
1. JSON serialization
2. UTF-8 encoding
3. gzip compression
4. base64 encoding

### Cache Chunking

When compressed cache exceeds `BOT_CACHE_CHUNK_SIZE` (55000 chars):
- Data is split across multiple bot comments
- Each chunk is stored in a separate comment
- Chunks are reassembled when loading cache

### Cache Contents

- `emoji`: Bot's reactions on comments (comment_id → reaction, source of truth)
- `fv`: File versions (filename::blob_sha → {ts: timestamp, cats: categories})
- `comments`: Processed comments (comment_id → CommentInfo with timestamp, first_line, ctype, categories, signed_files, user, locked)

**Note:** `current_file_versions` is NOT stored in cache - it's rebuilt from PR files every run by `update_file_states()`.

### Comment Processing

Comments are processed with the following logic:
- **Locked comments**: Skip processing entirely - signature data is already in cache and will be read by `compute_category_approval_states()`
- **Non-locked cached comments**: Re-process with `use_cached=True` to apply side effects (holds, labels, etc.) without setting reactions
- **Edited comments**: Delete from cache, re-process with `use_cached=False`
- **New comments**: Process with `use_cached=False`

This ensures that commands with side effects (like `hold`, `type`, `assign`) are re-applied on every run, while locked signatures are preserved.

## Bot Messages

### Message Markers

Bot comments include HTML comment markers to identify message types:
- Format: `<!--message_key-->` or `<!--message_key:comment_id-->`
- Used by `has_bot_comment(context, key)` to check if a message was already posted
- Prevents duplicate posting of the same message type

Common markers:
- `<!--welcome-->`: Welcome message
- `<!--fully_signed-->`: Fully-signed notification
- `<!--pr_updated:{hash}-->`: PR update notification (hash of commit SHA)
- `<!--ci_result_{context}_{url_hash}-->`: CI test result
- `<!--too_many_commits_warn-->`, `<!--too_many_commits_fail-->`: Commit count warnings
- `<!--too_many_files_warn-->`, `<!--too_many_files_fail-->`: File count warnings

### Welcome Message

Posted when a new PR/Issue is created (skipped for draft PRs), includes:
- Author mention
- For PRs: L2 signers of affected categories
- For Issues: `CMSSW_ISSUES_TRACKERS` members
- Available commands reference
- Unknown category warnings

**Message marker:** `<!--welcome-->` - used to detect if welcome message was already posted.

**Draft PR handling**: Welcome message is delayed until the PR exits draft state.

### Fully-Signed Message

Posted when a PR becomes fully-signed (first time `fully-signed` label is added):

```
This pull request is fully signed and it will be integrated in one of the next {branch} IBs{requiresTest}{devReleaseRelVal}. {autoMerge}
```

**Dynamic parts:**

| Variable | Possible Values |
|----------|-----------------|
| `branch` | Target branch (e.g., `master`, `CMSSW_14_0_X`) |
| `requiresTest` | ` (tests are also fine)` / ` (but tests are reportedly failing)` / ` (test failures were overridden)` / `` |
| `devReleaseRelVal` | ` and once validation in the development release cycle CMSSW_X_Y_X is complete` (for production branches) / `` |
| `autoMerge` | See below |

**Auto-merge message variants:**

| Condition | Message |
|-----------|---------|
| Ready to merge (tests + ORP OK) | `This pull request will be automatically merged.` |
| On hold | `This PR is put on hold by {blockers}. They have to unhold to remove the hold state or {managers} will have to merge it by hand.` |
| New package pending | `This pull request requires a new package and will not be merged. {managers}` |
| ORP approval pending | `This pull request will now be reviewed by the release team before it's merged. {managers} (and backports should be raised in the release meeting by the corresponding L2)` |

**Linked PRs notification:**

If the PR was tested with other PRs, an additional notice is appended:
```
**Notice** This PR was tested with additional Pull Request(s), please also merge them if necessary: {linked_prs}
```

And reminder comments are posted on those linked PRs:
```
**REMINDER** {managers}: This PR was tested with {this_pr}, please check if they should be merged together
```

### Status Updates

- Category approval status (✅ approved, ❌ rejected, ⏳ pending)
- Hold notifications
- Merge readiness

### Merge Conditions

A PR can be merged (`can_merge()` returns True) when ALL conditions are met:
1. PR is not in draft state
2. PR state is `fully-signed` (all L2 signatures approved)
3. No active holds
4. ORP approved (if in EXTRA_CHECKS)
5. Tests approved (if in EXTRA_CHECKS)
6. `new-package` approved (if in signing_categories)

### Status Message

The `generate_status_message()` function creates a summary including:
- PR state (fully-signed, merged, etc.)
- Category statuses with emoji indicators
- Active holds
- Merge readiness with reasons if not ready
- Labels

For merged PRs, shows "✅ **PR has been merged**" instead of merge conditions.

### Commit Update Notifications

Posted when the current state of PR files doesn't match the saved state (new commits pushed):

```
Pull request #{pr_number} was updated. {signers} can you please check and sign again.
```

If new categories are affected by the changes, the message includes additional information similar to the welcome message:
- New packages affected
- New categories and their L2 signers

**Note:** Notification is skipped for draft PRs.

## Label Management

### Automatic Labels

- File-pattern based labels via `CMSSW_LABELS`
- Type labels from `type`/`mtype` commands
- Status labels (tests-pending, tests-approved, etc.)

### Label Application

Labels are collected in `pending_labels` and applied in `update_pr_status()`.

## Repository Classification

### Repository Types

- **cmssw_repo**: `repo_name == GH_CMSSW_REPO` (main CMSSW repository)
- **cms_repo**: `repo_org in EXTERNAL_REPOS` (CMS organization repos)
- **external_repo**: `repo_name != CMSSW_REPO_NAME and repo_org in EXTERNAL_REPOS`

### External Repository Handling

For external repos:
- "externals" category is added to signing_categories
- Packages set to `{f"externals/{repo.full_name}"}`
- `external_to_package()` maps repo to additional packages
- CMSDIST repos validate branch against `VALID_CMSDIST_BRANCHES`

## Configuration

### Repository Config (`repo_config.py`)

- `CMSSW_CATEGORIES`: File-to-category mapping
- `CMSSW_L2`: Category-to-signers mapping
- `CMSSW_LABELS`: File-to-label patterns
- `CMSSW_ISSUES_TRACKERS`: Issue tracker users
- `PR_HOLD_MANAGERS`: Users who can place holds
- `TRIGGER_PR_TESTS`: Users who can trigger tests
- `PRE_CHECKS`: Categories required before tests
- `EXTRA_CHECKS`: Categories required for merge
- `IGNORE_ISSUES`: Issues to skip processing

## Thresholds

### Commit Limits
- `TOO_MANY_COMMITS_WARN_THRESHOLD`: 150 (warning)
- `TOO_MANY_COMMITS_FAIL_THRESHOLD`: 240 (block)

### File Limits (CMSSW repo only)
- `TOO_MANY_FILES_WARN_THRESHOLD`: 1500 (warning)
- `TOO_MANY_FILES_FAIL_THRESHOLD`: 3001 (block)

## Draft PR Handling

Draft PRs have special behavior:
- `@` mentions are disabled (uses plain usernames)
- Welcome message is delayed until PR exits draft state
- Re-sign notifications are skipped on commit updates
- Can be overridden with `<notify></notify>` tag

## Testing

### Test Framework

Tests use a custom mock framework:
- `MockGithub`, `MockRepository`, `MockIssue`, `MockPullRequest`
- JSON-based test data in `PRActionData/`
- Action recording/replay for verification

### Test Modes

- **Record Mode**: `pytest --record-actions` - saves expected actions
- **Verify Mode**: Default - compares against recorded actions

## File Structure

```
process_pr_v2.py          # Main implementation (~6750 lines)
test_process_pr_v2.py     # Test suite (~7850 lines)
conftest.py               # Pytest configuration
PRActionData/             # Test data and recorded actions
DESIGN.md                 # This design document
TESTING.md                # Testing documentation
```

## Dependencies

### External Modules
- `PyGithub`: GitHub API access
- `yaml`: Configuration parsing
- `gzip`, `base64`: Cache compression

### PyGithub Patches

The bot includes patches for known PyGithub bugs (controlled by `APPLY_PYGITHUB_PATCHES` flag):

**CommitCombinedStatus.statuses**: The original property doesn't handle pagination correctly for combined status, causing it to miss statuses when there are many. The patch returns a proper `PaginatedList`.

To disable patches once fixed upstream:
```python
APPLY_PYGITHUB_PATCHES = False
```

### CMS-SW Modules
- `categories`: Category definitions (CMSSW_L2, etc.)
- `cms_static`: Constants (BUILD_REL, etc.)
- `releases`: Release manager lookup
- `_py2with3compatibility`: Python 2/3 compatibility (run_cmd)

## Error Handling

### Early Exit Conditions

The bot may skip processing or return early for:
1. **No files changed**: PRs with `pr.changed_files == 0` are ignored
2. **Closed PR without jenkins status**: Don't create new `bot/{prId}/jenkins` status for closed PRs
3. **Invalid CMSDIST branch**: Skip PRs to branches not matching `VALID_CMSDIST_BRANCHES`
4. **Too many commits/files**: Block processing above threshold (can be overridden)
5. **Ignored issues**: Skip based on `IGNORE_ISSUES` config or `<cms-bot></cms-bot>` tag

### Graceful Degradation

- Missing data handled gracefully
- Detailed logging for debugging
- Dry-run mode for testing without side effects
- Force mode to override ignore flags

### Dry-Run Mode

When `dry_run=True`, the bot executes all processing logic but guards only the mutating API calls:
- `issue.create_comment()` → Logged but not executed
- `issue.edit()` → Logged but not executed
- `issue.add_to_labels()` / `remove_from_labels()` → Logged but not executed
- `commit.create_status()` → Logged but not executed
- `comment.edit()` / `comment.delete()` → Logged but not executed
- Property file creation → Logged but not written

This allows tests to verify full processing logic while preventing actual changes.

## Cache Key Types

**Important**: Cache keys are always strings, while GitHub object IDs are integers:
- `cache.comments[str(comment_id)]` - Keys are strings
- `cache.emoji[str(comment_id)]` - Keys are strings
- `comment.id` - Integer from GitHub API

When iterating cache and looking up in `context.comments`, convert appropriately:
```python
comment_id_int = int(comment_id)  # Convert cache key to int
for comment in context.comments:
    if comment.id == comment_id_int:
        ...
```