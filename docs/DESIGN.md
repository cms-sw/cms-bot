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
- `_commit_statuses`: Frozen cache of commit statuses at start of processing
- `pending_status_updates`: Dict mapping context_name → (sha, state, desc, url) for deferred updates
- `pending_bot_comments`: Queue of comments to post at end
- `pending_build_test_command`: Single pending build/test command (last one wins between build and test)
- `pending_labels`: Set of labels to add
- `pending_reactions`: Dict mapping comment_id → reaction to add

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

1. **File Detection**: When a PR is opened/updated, changed files are detected
2. **Category Assignment**: Files are mapped to categories via `categories_map.py`
3. **L2 Assignment**: Each category has L2 signers from `CMSSW_L2` configuration
4. **Signature Collection**: L2 signers approve/reject their categories
5. **File Tracking**: Each signature records the file versions for signed categories

### Signature Validation

A signature for a category is valid only if:
1. **No files changed**: All files that were signed are still current (same sha)
2. **No files added**: All current files in the category were covered by the signature

Example:
1. Category "core" has files [A::sha1, B::sha2]
2. User signs category "core" → records `signed_files: ["A::sha1", "B::sha2"]`
3. Signature becomes **invalid** if:
   - File A changes to A::sha3 (file changed)
   - File C::sha1 is added to category "core" (new file not signed)
4. Signature remains **valid** if:
   - File D is added to a different category
   - User's L2 membership changes

### Design Decisions

**File Reverts:** If a file is reverted to a previously-signed hash, L2 must re-sign. Old signatures are not re-used.

**Category Mapping Changes:** When a file is modified, its category mapping is recalculated using current rules. The mapping is only frozen while the file remains unchanged.

### Pre-Checks and Extra-Checks

- **PRE_CHECKS**: Categories that must be approved before tests can run (e.g., `code-checks`)
- **EXTRA_CHECKS**: Additional categories required for merge (e.g., ORP)

#### Pre-Check Status Tracking

Pre-checks have associated GitHub commit statuses with context `cms/{prId}/{precheck}`:

| State | Description | Trigger |
|-------|-------------|---------|
| `pending` | `{precheck} requested` | Auto-triggered when tests are triggered |
| `success` | `See details` | Pre-check signed with `+1` |
| `error` | `See details` | Pre-check rejected with `-1` |

The status URL points to the comment that last signed the pre-check category.

**Auto-triggering**: When tests are triggered (`create_test_property=True`), pre-checks without existing status are automatically triggered via `trigger_pending_pre_checks()`.

## Build/Test Command Processing

### Deferred Processing

Build and test commands are collected during comment processing and executed after all comments have been seen. This enables deduplication and "last one wins" semantics.

Commands are stored as a single item (not separate for build/test):
- `context.pending_build_test_command`: Last build or test command seen

**Why single slot?** Build and test commands write to the same properties file, so only one can actually be executed. Using "last one wins" prevents the PR from getting stuck if both commands are posted.

### Deduplication Rules

**Build commands**: 
- Check for `+1` reaction from bot in `handle_build_test` - if present, command is already processed
- Only the last build command is stored and executed

**Test commands**: 
- "Last one wins" - only the most recent test command is stored
- Skip if `bot/{prId}/jenkins` commit status URL matches the comment URL
- Skip if tests signature is not "pending" (tests already started or completed)

### Tests Approval State

The `tests` category has a special approval state determined by `_get_tests_approval_state()`:

| State | Condition |
|-------|-----------|
| `PENDING` | No test results, no "requested by" in jenkins status |
| `STARTED` | No test results, but jenkins status contains "requested by" |
| `APPROVED` | Required tests passed (or only optional tests passed) |
| `REJECTED` | Required tests failed (unless `ignore_tests_rejected` is set) |

The function checks `pending_status_updates` first for changes queued in the current run (e.g., abort command), then falls back to the frozen jenkins status.

### Jenkins Status Tracking

After successfully triggering a test command, the bot sets a commit status:
- Context: `bot/{prId}/jenkins`
- State: `success`
- Description: `Tests requested by {user} at {time} UTC.`
- Target URL: Comment URL that triggered the test

After abort command:
- State: `pending`
- Description: `Aborted, waiting for authorized user to issue the test command.`

This allows detecting if a test command was already processed and tracking test state.

### Commit Status Caching

The bot uses a **frozen cache** approach for commit statuses:
- `PRContext.get_commit_statuses()`: Returns frozen cache from start of processing
- `PRContext.get_commit_status(context_name)`: Gets a specific status from frozen cache
- Cache is populated once at the beginning of processing and NOT updated during the run

This ensures consistent behavior within a single processing run. Status changes take effect on the next bot invocation (triggered by webhooks).

### Deferred Status Updates

All commit status updates are queued during processing and executed at the end:
1. Functions call `context.queue_status_update(state, description, context_name, target_url, sha)`
2. Updates are stored in `pending_status_updates` dict (context_name → details)
3. Last update wins for each context (dict key overwrites)
4. At end of `process_pr()`, `flush_pending_statuses()` executes all queued updates
5. Only actually changed statuses are updated (compares against frozen cache)

### Checking Pending Updates

Some functions need to see status changes queued in the current run:
- `_get_pre_check_approval_state()`: Checks `pending_status_updates` first for pre-check signatures
- `_get_tests_approval_state()`: Checks `pending_status_updates` for jenkins status (e.g., after abort)
- `trigger_pending_pre_checks()`: Checks `pending_status_updates` to avoid re-triggering

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
- Pattern: `cms/<arch>/<test_type>/required` or `/optional`
- Tracks sub-statuses for build, relvals, etc.
- Posts results as +1/-1 comments when complete

## Cache System

### Cache Storage

Cache is stored in a special bot comment:
```
cms-bot internal usage<!-- {compressed_data} -->
```

### Compression

Cache data is compressed using:
1. JSON serialization
2. UTF-8 encoding
3. gzip compression
4. base64 encoding

### Cache Contents

- `emoji`: Bot's reactions on comments (comment_id → reaction, source of truth)
- `fv`: File versions (filename::sha → categories, timestamp)
- `comments`: Processed comments (comment_id → CommentInfo with timestamp, first_line, ctype, categories, signed_files, user, locked)

## Bot Messages

### Welcome Message

Posted when a new PR is created (skipped for draft PRs), includes:
- Author mention
- Assigned categories and L2 signers
- Available commands reference
- Unknown category warnings

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

- Category approval status (✅ approved, ❌ rejected, ⏳ pending, 🔄 started)
- Hold notifications
- Merge readiness

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

### CMS-SW Modules
- `categories`: Category definitions (CMSSW_L2, etc.)
- `cms_static`: Constants (BUILD_REL, etc.)
- `releases`: Release manager lookup
- `_py2with3compatibility`: Python 2/3 compatibility (run_cmd)

## Error Handling

- Graceful degradation on missing data
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