# Implementing New Commands in process_pr_v2.py

This document describes how to implement new commands and the important patterns to follow.

## Command Registration

Commands are registered using the `@command` decorator:

```python
@command(
    "command_name",           # Unique identifier for the command
    r"^regex_pattern$",       # Pattern to match (first line of comment)
    description="...",        # Description for help/debugging
    pr_only=False,            # Set True if command only works on PRs (not Issues)
)
def handle_command_name(
    context: PRContext,
    match: re.Match,
    user: str,
    comment_id: int,
    timestamp: datetime,
) -> Optional[bool]:
    """
    Handle the command.
    
    Returns:
        True: Command was processed successfully
        False: Command was recognized but failed (e.g., no permission)
        None: Command pattern matched but this isn't actually a command (fallthrough)
    """
    ...
```

## Deferred Actions Pattern

**IMPORTANT**: Command handlers should NOT directly call GitHub API methods to modify state. Instead, use the deferred action queues to ensure consistent processing.

### Why Deferred Actions?

1. **Frozen Cache Consistency**: The bot uses frozen caches (e.g., commit statuses) during processing. Direct modifications would make the cache inconsistent with reality.

2. **Deduplication**: Multiple commands might queue the same action. Deferred queues handle "last one wins" semantics.

3. **Atomic Batch Updates**: All changes are applied together at the end, reducing API calls and race conditions.

4. **Dry-Run Support**: Deferred actions can be logged instead of executed in dry-run mode.

### Deferred Action Types

| Action Type | Queue/Method | Applied By |
|-------------|--------------|------------|
| Labels | `context.pending_labels.add(label)` | `update_pr_status()` |
| Commit Statuses | `context.queue_status_update(...)` | `flush_pending_statuses()` |
| Comments | `queue_bot_comment(context, message)` | `flush_pending_comments()` |
| Reactions | `context.pending_reactions[comment_id] = reaction` | End of `process_pr()` |
| Build Commands | `context.pending_build_command = (...)` | `process_pending_build_test_commands()` |
| Test Commands | `context.pending_test_command = (...)` | `process_pending_build_test_commands()` |

### Example: Adding a Label

```python
@command("urgent", r"^urgent$", description="Mark PR as urgent")
def handle_urgent(context, match, user, comment_id, timestamp):
    # DON'T do this:
    # context.issue.add_to_labels("urgent")  # WRONG!
    
    # DO this instead:
    context.pending_labels.add("urgent")
    return True
```

### Example: Setting a Commit Status

```python
@command("approve_checks", r"^\+code-checks$", description="Approve code checks")
def handle_approve_checks(context, match, user, comment_id, timestamp):
    # DON'T do this:
    # commit.create_status(state="success", ...)  # WRONG!
    
    # DO this instead:
    pr_id = context.issue.number
    context.queue_status_update(
        state="success",
        description="See details",
        context_name=f"cms/{pr_id}/code-checks",
        target_url=comment_url,
    )
    return True
```

### Example: Posting a Comment

```python
@command("notify", r"^notify\s+(.+)$", description="Send notification")
def handle_notify(context, match, user, comment_id, timestamp):
    message = match.group(1)
    
    # DON'T do this:
    # context.issue.create_comment(f"Notification: {message}")  # WRONG!
    
    # DO this instead:
    queue_bot_comment(context, f"Notification: {message}")
    return True
```

## Special Cases: Immediate Actions

In rare cases, actions need to happen immediately rather than being deferred:

### 1. Reactions on the Current Comment

Reactions are typically added immediately to provide feedback to the user:

```python
# Adding reaction to current comment is OK to do immediately
# (though context.pending_reactions is preferred)
for comment in context.comments:
    if comment.id == comment_id:
        comment.create_reaction("+1")
        break
```

However, the bot tracks reactions in `context.cache.emoji` as the source of truth, so prefer using `context.pending_reactions` when possible.

### 2. Cache Updates

Updates to the bot's internal cache (`context.cache`) happen immediately since they're local state:

```python
# Cache updates are immediate (local state)
context.cache.comments[str(comment_id)] = CommentInfo(
    timestamp=timestamp.isoformat(),
    first_line="+1",
    ctype="+1",
    categories=categories,
    signed_files=signed_files,
    user=user,
)
```

### 3. Context Flags

Setting flags on the context is immediate since they're local state:

```python
# Context flags are immediate
context.abort_tests = True
context.should_merge = True
context.must_close = True
```

## Checking Current State

### Frozen Cache

When checking current state, use the frozen cache methods:

```python
# Get frozen commit statuses (from start of processing)
statuses = context.get_commit_statuses()
status = context.get_commit_status("cms/123/code-checks")
```

### Checking Pending Updates

If you need to see changes queued in the current run, check `pending_status_updates`:

```python
# Check if status was already queued in this run
status_context = f"cms/{pr_id}/code-checks"
if status_context in context.pending_status_updates:
    sha, state, description, target_url = context.pending_status_updates[status_context]
    # Use queued state
else:
    # Fall back to frozen cache
    status = context.get_commit_status(status_context)
```

## Permission Checking

Commands should verify the user has permission before taking action:

```python
@command("hold", r"^hold$", description="Place hold on PR")
def handle_hold(context, match, user, comment_id, timestamp):
    # Check permissions first
    if not can_place_hold(context, user):
        logger.info(f"User {user} not authorized to place hold")
        return False
    
    # Then perform the action
    context.pending_labels.add("hold")
    return True
```

Common permission checks:
- `is_valid_tester(context, user)` - Can trigger tests
- `get_user_l2_categories(repo_config, user, timestamp)` - L2 categories user can sign
- Check against `TRIGGER_PR_TESTS`, `PR_HOLD_MANAGERS`, `CMSSW_ISSUES_TRACKERS`, etc.

## Build/Test Commands

Build and test commands have special handling due to deduplication requirements:

```python
@command("test", r"^test(\s+.*)?$", description="Trigger tests")
def handle_build_test(context, match, user, comment_id, timestamp):
    # Parse the command
    result = parse_test_cmd(first_line)
    
    # For build: check if already processed (has +1 reaction)
    if result.verb == "build":
        reactions = get_comment_reactions(context, comment_id)
        if "+1" in reactions:
            return True  # Already processed
    
    # Store as pending (last one wins)
    if result.verb == "build":
        context.pending_build_command = (comment_id, user, timestamp, result)
    else:
        context.pending_test_command = (comment_id, user, timestamp, result)
    
    return True
```

The actual execution happens in `process_pending_build_test_commands()` after all comments are processed.

## Timestamp Handling

For commands that are invalidated by new commits (like signatures), check the timestamp:

```python
# Skip if command was made before the latest commit
latest_commit_ts = get_latest_commit_timestamp(context)
if latest_commit_ts and timestamp < latest_commit_ts:
    logger.debug(f"Skipping command - before latest commit")
    return True  # Command recognized but not applicable
```

## Testing Commands

When writing tests for new commands:

1. Use `create_basic_pr_data()` to set up test fixtures
2. Use `dryRun=False` to actually record actions
3. Use `FunctionHook(recorder.property_file_hook())` to capture property file creation
4. Check `recorder.actions` for expected actions

```python
def test_my_command(self, record_mode):
    create_basic_pr_data("test_my_command", pr_number=1, comments=[...])
    
    recorder = ActionRecorder("test_my_command", record_mode)
    gh = MockGithub("test_my_command", recorder)
    repo = MockRepository("test_my_command", recorder=recorder)
    issue = MockIssue("test_my_command", number=1, recorder=recorder)
    
    with FunctionHook(recorder.property_file_hook()):
        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dryRun=False,
            cmsbuild_user="cmsbuild",
            loglevel="DEBUG",
        )
    
    # Verify expected actions
    label_actions = [a for a in recorder.actions if a["action"] == "add_labels"]
    assert "my-label" in label_actions[0]["details"]["labels"]
```

## Summary

| Do | Don't |
|----|-------|
| `context.pending_labels.add(label)` | `issue.add_to_labels(label)` |
| `context.queue_status_update(...)` | `commit.create_status(...)` |
| `queue_bot_comment(context, msg)` | `issue.create_comment(msg)` |
| `context.pending_reactions[id] = reaction` | Direct reaction calls (usually OK) |
| Check `pending_status_updates` first | Assume frozen cache is current |
| Return `True`/`False`/`None` appropriately | Raise exceptions for normal flow |