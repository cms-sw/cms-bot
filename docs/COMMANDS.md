# Implementing New Commands in process_pr_v2.py

This document describes how to implement new commands and the important patterns to follow.

## Command Registration

Commands are registered using the `@command` decorator:

```python
@command(
    "command_name",           # Unique identifier for the command
    r"^regex_pattern$",       # Pattern to match against the first line of the comment
    description="...",        # Description for help/debugging
    pr_only=False,            # Set True if command only works on PRs (not Issues)
    acl=lambda u: ...,        # Access control: receives a CommandUser, returns bool
    reset_on_push=False,      # If True, command is invalidated by new commits
)
def handle_command_name(
    context: PRContext,
    match: re.Match,
    comment: Any,             # The full comment object (comment.user.login, comment.id, etc.)
) -> Optional[bool]:
    """
    Handle the command.

    Returns:
        True: Command was processed successfully → :+1: reaction
        False: Command was recognized but failed (no permission, bad args, etc.) → :-1: reaction
        None: Pattern matched but this isn't actually this command (fallthrough to next match)
    """
    user = comment.user.login
    comment_id = comment.id
    timestamp = get_comment_timestamp(comment)
    ...
```

### CommandUser (ACL helper)

The `acl=` lambda receives a `CommandUser` instance with these properties:

| Property | Type | Description |
|---|---|---|
| `login` | `str` | GitHub username |
| `user_categories` | `list[str]` | L2 categories the user belongs to at comment time |
| `is_valid_commenter` | `bool` | L2 member, release manager, or granted test rights |
| `is_release_manager` | `bool` | In current release manager list |
| `is_pr_hold_manager` | `bool` | In `PR_HOLD_MANAGERS` config |
| `is_orp` | `bool` | In ORP (operations) role |
| `is_requestor` | `bool` | Is the PR author |
| `is_cmsbuild_user` | `bool` | Is the bot (`cmsbuild_user`) |
| `is_issue_tracker` | `bool` | In `CMSSW_ISSUES_TRACKERS` config |

Common ACL patterns:
```python
acl=lambda u: bool(u.user_categories)                            # any L2
acl=lambda u: bool(u.user_categories) or u.is_release_manager   # L2 or RM
acl=lambda u: u.is_release_manager or u.is_pr_hold_manager or bool(u.user_categories)
acl=is_valid_tester                                              # testers (see below)
acl=lambda u: u.is_release_manager or u.is_orp                  # merge/close
```

`is_valid_tester(user)` returns `True` if the user is in `TRIGGER_PR_TESTS`, has L2
categories, is a release manager, or has been granted test rights via `allow @user test rights`.

## Deferred Actions Pattern

**IMPORTANT**: Command handlers must NOT directly call GitHub API methods to modify state.
Instead, use the deferred action queues to ensure consistent processing.

### Why Deferred Actions?

1. **Frozen Cache Consistency**: The bot uses frozen caches (e.g., commit statuses) during
   processing. Direct modifications would make the cache inconsistent.
2. **Deduplication**: Multiple commands might queue the same action. Deferred queues handle
   "last one wins" semantics automatically.
3. **Atomic Batch Updates**: All changes are applied together at the end, reducing API calls
   and race conditions.
4. **Dry-Run Support**: Deferred actions can be logged instead of executed.

### Deferred Action Types

| What you want | How to queue it | Applied by |
|---|---|---|
| Add a label | `context.pending_labels.add(label)` | `update_pr_status()` |
| Remove a label | `context.pending_labels_to_remove.add(label)` | `update_pr_status()` |
| Post a comment | `post_bot_comment(context, message, key, dedup_hash)` | `flush_pending_comments()` |
| Set a commit status | `context.queue_status_update(state, description, context_name, target_url)` | `flush_pending_statuses()` |
| Set a reaction | Returned `True`/`False` from handler | `set_comment_reaction()` in `process_comment()` |

### Example: Adding a Label

```python
@command("urgent", r"^urgent$", description="Mark PR as urgent",
         acl=lambda u: bool(u.user_categories))
def handle_urgent(context, match, comment):
    # DON'T do this:
    # context.issue.add_to_labels("urgent")  # WRONG

    # DO this:
    context.pending_labels.add("urgent")
    return True
```

### Example: Setting a Commit Status

```python
@command("approve_checks", r"^\+code-checks$", description="Approve code checks",
         acl=lambda u: u.is_cmsbuild_user)
def handle_approve_checks(context, match, comment):
    # DON'T do this:
    # commit.create_status(state="success", ...)  # WRONG

    # DO this:
    pr_id = context.issue.number
    comment_url = get_comment_url(context, comment.id)
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
@command("notify", r"^notify\s+(.+)$", description="Send notification",
         acl=lambda u: bool(u.user_categories))
def handle_notify(context, match, comment):
    message = match.group(1)

    # DON'T do this:
    # context.issue.create_comment(f"Notification: {message}")  # WRONG

    # DO this:
    post_bot_comment(context, f"Notification: {message}", key="notify",
                     dedup_hash=deterministic_hash(message))
    return True
```

## Immediate Actions (Exceptions to Deferred Pattern)

### Cache Updates

Updates to `context.cache` are immediate — they are local state that will be saved
to comments at the end:

```python
context.cache.comments[str(comment_id)] = CommentInfo(
    timestamp=timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
    first_line="+1",
    ctype="+1",
    categories=categories,
    signed_files=signed_files,
    user=user,
)
```

### Context Flags

Setting flags on the context object is immediate:

```python
context.abort_tests = True
context.should_merge = True
context.must_close = True
context.granted_test_rights.add(target_user)
```

## Checking Current State

### Frozen Commit Statuses

During a processing run, commit statuses are read once and cached. Always use the
frozen cache methods to check status:

```python
statuses = context.get_commit_statuses()   # Dict[context_name, status_object]
status = context.get_commit_status("cms/123/code-checks")
```

### Checking Pending Updates

If you need to see status changes queued earlier in the current run, check
`pending_status_updates`:

```python
status_context = f"cms/{pr_id}/code-checks"
if status_context in context.pending_status_updates:
    _, state, description, target_url = context.pending_status_updates[status_context]
else:
    status = context.get_commit_status(status_context)
```

## Approval / Signature Commands

Approval and rejection go through `_handle_approval()`, which enforces:

- **Pre-check categories** (e.g., `code-checks`): only the bot user (`cmsbuild_user`)
  can sign these; they update a GitHub commit status directly.
- **Regular L2 categories** (e.g., `core`, `simulation`): the user must actually belong
  to the category at comment time (checked via `get_user_l2_categories()`). Signing for
  a category you don't belong to returns `False` → `:-1:` reaction.
- **Generic `+1`/`-1`**: applies to all the user's L2 categories at that time.

## Timestamp Handling

For commands that are invalidated by new commits, use `reset_on_push=True` in the
decorator, or check manually:

```python
latest_commit_ts = get_latest_commit_timestamp(context)
if latest_commit_ts and timestamp < latest_commit_ts:
    logger.debug("Skipping command - before latest commit")
    return True  # Recognized but not applicable
```

## Build/Test Commands

Build and test commands have special handling due to deduplication requirements.
They are stored as a single slot (last one wins between any build/test commands):

```python
context.pending_build_test_command = (comment, result)
```

The actual execution happens in `process_pending_build_test_commands()` after all
comments are processed.

**Deduplication rules:**
- **Build**: skipped if the comment already has a `+1` reaction from the bot
- **Test**: skipped if `bot/{prId}/jenkins` status URL matches the comment URL (already triggered)

## L2 Data Initialization

L2 data (which users belong to which categories) is loaded from `l2.json` via
`init_l2_data(repo_config, cms_repo)`. This is called automatically at the start of
each `process_pr()` invocation.

`init_l2_data` is a no-op if `_L2_DATA` is already populated — tests pre-populate it
via the `setup_l2_data` autouse fixture, so the file is never read during testing.

## Summary

| Do | Don't |
|---|---|
| `context.pending_labels.add(label)` | `issue.add_to_labels(label)` |
| `context.queue_status_update(...)` | `commit.create_status(...)` |
| `post_bot_comment(context, msg, ...)` | `issue.create_comment(msg)` |
| Return `True`/`False`/`None` | Raise exceptions for normal flow |
| Check `pending_status_updates` first | Assume frozen cache is current |
| Use `comment.user.login`, `comment.id` | Separate `user`, `comment_id` parameters |
