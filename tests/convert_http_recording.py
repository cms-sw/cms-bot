#!/usr/bin/env python3
"""
Convert recorded HTTP requests/responses to test data JSON format.

This tool reads a file containing recorded HTTP interactions from PyGithub
and converts them to the JSON format used by our test mocks.

Input format (one request/response per record, fields separated by newlines):
    protocol (https)
    method (GET/POST/etc)
    host (api.github.com)
    port (None or number)
    path (/repos/owner/repo)
    headers (dict repr)
    body (None or content)
    status_code (200)
    response_headers (list of tuples repr)
    response_body (JSON string)

Output: JSON files organized by endpoint type in ReplayData/<test_name>/ directory.

Additional processing:
- Adds hidden markers to bot comments to match new process_pr_v2 format
- Converts old bot cache format to new format
"""

import argparse
import ast
import base64
import json
import re
import sys
import zlib
from datetime import timezone, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

this_script = Path(__file__)
sys.path.insert(0, str(this_script.parent.parent))
sys.path.insert(0, str(this_script.parent.parent / "repos" / "iarspider-cmssw" / "cmssw"))

import repo_config
from process_pr_v2 import (
    initialize_labels,
    init_l2_data,
    get_file_l2_categories,
    get_user_l2_categories,
    parse_timestamp,
)

initialize_labels(repo_config)
init_l2_data(repo_config, True)

# Bot username patterns (can be expanded)
BOT_USERNAMES = {"iarspider"}

# Cache comment marker (must match process_pr_v2.py)
CMSBOT_TECHNICAL_MSG = "cms-bot internal usage"
CACHE_COMMENT_MARKER = CMSBOT_TECHNICAL_MSG + "<!-- bot cache:"
NEW_CACHE_COMMENT_MARKER = CMSBOT_TECHNICAL_MSG + "<!--"
CACHE_COMMENT_END = "-->"


def parse_recording_file(filepath: Path) -> List[Dict[str, Any]]:
    """
    Parse a recording file and return list of request/response records.

    Each record has 10 lines:
    1. protocol
    2. method
    3. host
    4. port
    5. path
    6. headers
    7. body
    8. status_code
    9. response_headers
    10. response_body
    """
    records = []

    with open(filepath, "r") as f:
        content = f.read()

    # Split into lines, handling the fact that response_body may contain newlines
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        # Skip empty lines between records
        while i < len(lines) and not lines[i].strip():
            i += 1

        if i >= len(lines):
            break

        # Read the 10 fields
        try:
            protocol = lines[i].strip()
            i += 1
            method = lines[i].strip()
            i += 1
            host = lines[i].strip()
            i += 1
            port = lines[i].strip()
            i += 1
            path = lines[i].strip()
            i += 1
            headers = lines[i].strip()
            i += 1
            request_body = lines[i].strip()
            i += 1
            status_code = lines[i].strip()
            i += 1
            response_headers = lines[i].strip()
            i += 1

            # Response body might span multiple lines until next record starts
            # or end of file. We detect next record by seeing 'https' or 'http'
            response_body_lines = []
            while i < len(lines):
                line = lines[i]
                # Check if this looks like start of new record
                if line.strip() in ("https", "http") and i + 9 < len(lines):
                    # Peek ahead to see if next lines look like a record
                    next_line = lines[i + 1].strip()
                    if next_line in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
                        break
                response_body_lines.append(line)
                i += 1

            response_body = "\n".join(response_body_lines).strip()

            record = {
                "protocol": protocol,
                "method": method,
                "host": host,
                "port": None if port == "None" else int(port),
                "path": path,
                "headers": ast.literal_eval(headers) if headers != "None" else None,
                "request_body": None if request_body == "None" else request_body,
                "status_code": int(status_code),
                "response_headers": (
                    ast.literal_eval(response_headers) if response_headers != "None" else None
                ),
                "response_body": response_body,
            }
            records.append(record)

        except (IndexError, ValueError) as e:
            print(f"Warning: Failed to parse record at line {i}: {e}", file=sys.stderr)
            # Try to skip to next record
            i += 1
            continue

    return records


def parse_response_body(body: str) -> Any:
    """Parse JSON response body, handling edge cases."""
    if not body or body == "None":
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def extract_endpoint_info(path: str) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Extract endpoint type and identifiers from path.

    Returns: (endpoint_type, owner_repo, number)

    Examples:
        /repos/owner/repo -> ('Repository', 'owner_repo', None)
        /repos/owner/repo/pulls/123 -> ('PullRequest', 'owner_repo', 123)
        /repos/owner/repo/issues/123 -> ('Issue', 'owner_repo', 123)
        /repos/owner/repo/pulls/123/files -> ('PullRequestFiles', 'owner_repo', 123)
        /repos/owner/repo/pulls/123/commits -> ('PullRequestCommits', 'owner_repo', 123)
        /repos/owner/repo/issues/123/comments -> ('IssueComments', 'owner_repo', 123)
    """
    # Remove query parameters for matching
    path_no_query = path.split("?")[0]

    # Rate limit (can be ignored)
    if path_no_query == "/rate_limit":
        return "RateLimit", None, None

    # Repository
    match = re.match(r"^/repos/([^/]+)/([^/]+)$", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "Repository", owner_repo, None

    # Pull Request
    match = re.match(r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)$", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "PullRequest", owner_repo, int(match.group(3))

    # Pull Request Files
    match = re.match(r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)/files", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "PullRequestFiles", owner_repo, int(match.group(3))

    # Pull Request Commits
    match = re.match(r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)/commits", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "PullRequestCommits", owner_repo, int(match.group(3))

    # Pull Request Reviews
    match = re.match(r"^/repos/([^/]+)/([^/]+)/pulls/(\d+)/reviews", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "PullRequestReviews", owner_repo, int(match.group(3))

    # Issue
    match = re.match(r"^/repos/([^/]+)/([^/]+)/issues/(\d+)$", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "Issue", owner_repo, int(match.group(3))

    # Issue Comments
    match = re.match(r"^/repos/([^/]+)/([^/]+)/issues/(\d+)/comments", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "IssueComments", owner_repo, int(match.group(3))

    # Issue Labels
    match = re.match(r"^/repos/([^/]+)/([^/]+)/issues/(\d+)/labels", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "IssueLabels", owner_repo, int(match.group(3))

    # Issue/Comment Reactions
    match = re.match(r"^/repos/([^/]+)/([^/]+)/issues/comments/(\d+)/reactions", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "CommentReactions", owner_repo, int(match.group(3))

    # Milestone
    match = re.match(r"^/repos/([^/]+)/([^/]+)/milestones/(\d+)", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "Milestone", owner_repo, int(match.group(3))

    # Compare (commit ranges)
    match = re.match(r"^/repos/([^/]+)/([^/]+)/compare/([^/]+)\.\.\.([^/]+)", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        # Use base...head as identifier
        return "Compare", owner_repo, f"{match.group(3)}...{match.group(4)}"

    # Commit Status (combined status)
    match = re.match(r"^/repos/([^/]+)/([^/]+)/commits/([a-f0-9]+)/status", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "CommitCombinedStatus", owner_repo, match.group(3)

    # Commit Statuses (individual statuses, via /statuses/ endpoint)
    match = re.match(r"^/repos/([^/]+)/([^/]+)/statuses/([a-f0-9]+)", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "CommitStatus", owner_repo, match.group(3)

    # Git Commit (different from regular commit - has git/ in path)
    match = re.match(r"^/repos/([^/]+)/([^/]+)/git/commits/([a-f0-9]+)", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "GitCommit", owner_repo, match.group(3)

    # Commit
    match = re.match(r"^/repos/([^/]+)/([^/]+)/commits/([a-f0-9]+)$", path_no_query)
    if match:
        owner_repo = f"{match.group(1)}_{match.group(2)}"
        return "Commit", owner_repo, match.group(3)

    # Repository by ID - Pull Request Files (paginated)
    match = re.match(r"^/repositories/(\d+)/pulls/(\d+)/files", path_no_query)
    if match:
        return "RepoIdPullRequestFiles", match.group(1), int(match.group(2))

    # Repository by ID - Pull Request Commits (paginated)
    match = re.match(r"^/repositories/(\d+)/pulls/(\d+)/commits", path_no_query)
    if match:
        return "RepoIdPullRequestCommits", match.group(1), int(match.group(2))

    # Repository by ID - Commits (paginated, usually for commit history)
    match = re.match(r"^/repositories/(\d+)/commits/([a-f0-9]+)", path_no_query)
    if match:
        return "RepoIdCommits", match.group(1), match.group(2)

    # User
    match = re.match(r"^/users/([^/]+)$", path_no_query)
    if match:
        return "User", match.group(1), None

    # Organization
    match = re.match(r"^/orgs/([^/]+)$", path_no_query)
    if match:
        return "Organization", match.group(1), None

    # Unknown
    return "Unknown", path, None


def is_bot_comment(comment: Dict[str, Any]) -> bool:
    """Check if a comment is from a bot user."""
    user = comment.get("user", {})
    login = user.get("login", "").lower()
    return login in BOT_USERNAMES


def detect_comment_type(body: str, comment_id: int) -> Optional[str]:
    """
    Detect the type of bot comment based on its content.

    Returns the message_key that should be used as a marker, or None if not a recognized bot message.
    """
    if not body:
        return None

    first_line = body.split("\n")[0].strip().lower()

    # Welcome message
    if "a new" in first_line or "has been submitted by" in first_line:
        return "welcome"

    # PR updated message
    if "was updated" in first_line and "pull request" in first_line:
        # We can't determine the exact hash, so use a placeholder
        return "pr_updated:converted"

    # Hold message
    if "put on hold" in first_line:
        return f"hold:{comment_id}"

    # Assign message
    if "new categories assigned" in first_line:
        return f"assign:{comment_id}"

    # Issue fully signed
    if "fully signed" in first_line:
        return "issue_fully_signed"

    # Too many commits/files messages
    if "too many commits" in first_line:
        return "too_many_commits_fail"
    if "contains many commits" in first_line:
        return "too_many_commits_warn"
    if "too many files" in first_line or "touches too many files" in first_line:
        return "too_many_files_fail"
    if "touches many files" in first_line:
        return "too_many_files_warn"

    # CI test result (+1 or -1 at start)
    if body.strip().startswith("+1") or body.strip().startswith("-1"):
        # These are CI results, use a generic key
        return f"ci_result:converted:{comment_id}"

    return None


def add_bot_comment_marker(comment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a hidden marker to bot comments if they don't already have one.

    Modifies the comment body to include <!--message_key--> marker.
    """
    if not is_bot_comment(comment):
        return comment

    body = comment.get("body", "")
    if not body:
        return comment

    # Skip if already has a marker
    if "<!--" in body and "-->" in body:
        return comment

    # Skip cache comments (they have their own format)
    if CMSBOT_TECHNICAL_MSG in body:
        return comment

    comment_id = comment.get("id", 0)
    message_key = detect_comment_type(body, comment_id)

    if message_key:
        # Add marker at the end
        comment = comment.copy()
        comment["body"] = f"{body}\n<!--{message_key}-->"

    return comment


def parse_old_cache(body: str) -> Optional[Dict[str, Any]]:
    """
    Parse old-style bot cache from comment body.

    Old format: '<cmsbot-technical-message><!-- {json_or_compressed} -->'
    Compressed format uses 'b64:' prefix before base64-encoded zlib data.
    Returns parsed data or None if not a cache comment or can't parse.
    """
    if CMSBOT_TECHNICAL_MSG not in body:
        return None

    # Extract the data between markers
    start = body.find(CACHE_COMMENT_MARKER)
    if start == -1:
        return None

    start += len(CACHE_COMMENT_MARKER)
    end = body.rfind(CACHE_COMMENT_END)
    if end == -1 or end <= start:
        return None

    data_str = body[start:end].strip()

    # Check for b64: prefix (compressed data)
    if data_str.startswith("b64:"):
        try:
            compressed = base64.decodebytes(data_str[4:].encode())
            decompressed = zlib.decompress(compressed)
            return json.loads(decompressed.decode("utf-8"))
        except Exception:
            pass

    # Try to parse as plain JSON
    try:
        return json.loads(data_str)
    except json.JSONDecodeError:
        pass

    return None


def convert_old_cache_to_new(
    old_cache: Dict[str, Any],
    commits_data: List[Dict[str, Any]],
    all_comments: Dict[int, Dict[str, Any]],
    pr_files_data: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert old-style bot cache to new format.

    Old format:
    {
        "emoji": {},
        "signatures": { "<comment_id>": "<commit_sha>" },
        "commits": { "<sha>": {"squashed": bool, "time": ts, "files": [...]} }
    }

    New format:
    {
        "emoji": {},
        "fv": { "<filename>::<sha>": {"ts": ..., "cats": [...]} },
        "comments": { "<comment_id>": {"ts": ..., "first_line": ..., "ctype": ..., "cats": ..., "signed_files": ..., "user": ...} }
    }

    Args:
        old_cache: The old cache data
        commits_data: List of commit dicts from PullRequestCommits endpoint
        all_comments: Dict mapping comment_id -> comment dict (for first_line lookup)
        pr_files_data: List of file dicts from PullRequestFiles endpoint (has real blob SHAs)
    """
    new_cache = {
        "emoji": old_cache.get("emoji", {}),
        "fv": {},
        "comments": {},
    }

    # Build commit SHA to files mapping from commits_data
    commit_files = {}
    for commit in commits_data:
        sha = commit.get("sha", "")
        if sha:
            files = commit.get("files", [])
            file_list = []
            for f in files:
                filename = f.get("filename", "")
                if filename:
                    file_list.append(filename)
            commit_files[sha] = file_list

    # Determine head commit SHA (last commit in commits_data, sorted by date)
    head_commit_sha = None
    if commits_data:
        # Commits are typically in chronological order, last one is head
        head_commit_sha = commits_data[-1].get("sha", "")

    # Build filename -> blob_sha mapping from pr_files_data (these are for head commit)
    head_file_shas = {}
    if pr_files_data:
        for f in pr_files_data:
            filename = f.get("filename", "")
            blob_sha = f.get("sha", "")
            if filename and blob_sha:
                head_file_shas[filename] = blob_sha

    # Convert signatures to file versions
    signatures = old_cache.get("signatures", {})
    commits_info = old_cache.get("commits", {})

    for comment_id, commit_sha in signatures.items():
        # Get files for this commit
        files = []
        if commit_sha in commits_info:
            files = commits_info[commit_sha].get("files", [])
        elif commit_sha in commit_files:
            files = commit_files[commit_sha]

        # Get comment info from all_comments
        comment_id_int = int(comment_id)
        comment_data = all_comments.get(comment_id_int, {})

        # Get timestamp from comment (ISO format string)
        ts = comment_data.get("created_at", "")

        # Parse timestamp for category lookup
        ts_dt = None
        if ts:
            try:
                ts_dt = parse_timestamp(ts)
            except Exception:
                ts_dt = datetime.now(timezone.utc)
        else:
            ts_dt = datetime.now(timezone.utc)

        # Check if this signature is for the head commit
        is_head_commit = commit_sha == head_commit_sha

        # Build signed_files as filename::blob_sha keys
        signed_file_keys = []
        for filename in files:
            # For head commit, use real blob SHA if available
            if is_head_commit and filename in head_file_shas:
                blob_sha = head_file_shas[filename]
                key = f"{filename}::{blob_sha}"
            else:
                # For older commits, use synthetic key (signature will be invalidated anyway)
                key = f"{filename}::commit::{commit_sha[:12]}"

            signed_file_keys.append(key)
            if key not in new_cache["fv"]:
                new_cache["fv"][key] = {
                    "ts": ts,
                    "cats": get_file_l2_categories(repo_config, filename, ts_dt),
                }

        # Get first_line and detect ctype from comment body
        body = comment_data.get("body", "")
        first_line = ""
        ctype = None
        cats = []

        if body:
            first_line = body.split("\n")[0].strip()
            first_line_lower = first_line.lower()

            # Parse signature: +1, -1, +<category>, -<category>
            if first_line_lower == "+1":
                ctype = "+1"
                first_line = "+1"
            elif first_line_lower == "-1":
                ctype = "-1"
                first_line = "-1"
            elif first_line.startswith("+") and len(first_line) > 1:
                # +<category>
                ctype = "+1"
                cat = first_line[1:].strip()
                cats = [cat]
            elif first_line.startswith("-") and len(first_line) > 1:
                # -<category>
                ctype = "-1"
                cat = first_line[1:].strip()
                cats = [cat]

        # Get user from comment
        user = None
        user_data = comment_data.get("user", {})
        if user_data:
            user = user_data.get("login", "")

        # For generic +1/-1, get user's L2 categories at that time
        if ctype in ("+1", "-1") and not cats and user:
            cats = get_user_l2_categories(repo_config, user, ts_dt)

        # Create comment entry with all required fields
        new_cache["comments"][str(comment_id)] = {
            "ts": ts,
            "first_line": first_line,
            "ctype": ctype,
            "cats": cats,
            "signed_files": signed_file_keys,
            "user": user,
        }

    return new_cache


BOT_CACHE_CHUNK_SIZE = 55000


def convert_cache_comment(
    comment: Dict[str, Any],
    commits_data: List[Dict[str, Any]],
    all_comments: Dict[int, Dict[str, Any]],
    pr_files_data: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert a cache comment from old format to new format.

    Note: This only converts a single cache comment. In reality, cache may span
    multiple comments, but for conversion purposes we handle each independently.

    Args:
        comment: The cache comment to convert
        commits_data: List of commit dicts from PullRequestCommits endpoint
        all_comments: Dict mapping comment_id -> comment dict (for first_line lookup)
        pr_files_data: List of file dicts from PullRequestFiles endpoint (has real blob SHAs)
    """
    body = comment.get("body", "")
    old_cache = parse_old_cache(body)

    if old_cache is None:
        return comment

    # Check if already in new format (has "fv" or "comments" keys)
    if "fv" in old_cache or "comments" in old_cache:
        return comment  # Already new format

    # Convert to new format
    new_cache = convert_old_cache_to_new(old_cache, commits_data, all_comments, pr_files_data)

    # Serialize (compress if larger than chunk size, like old code but without b64: prefix)
    new_cache_json = json.dumps(new_cache, separators=(",", ":"), sort_keys=True)

    if len(new_cache_json) > BOT_CACHE_CHUNK_SIZE:
        compressed = zlib.compress(new_cache_json.encode("utf-8"))
        new_cache_str = base64.b64encode(compressed).decode("ascii")
    else:
        new_cache_str = new_cache_json

    # Update comment body
    new_body = f"{NEW_CACHE_COMMENT_MARKER} {new_cache_str} {CACHE_COMMENT_END}"

    comment = comment.copy()
    comment["body"] = new_body

    return comment


def process_comments(
    comments: List[Dict[str, Any]],
    commits_data: List[Dict[str, Any]],
    pr_files_data: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Process all comments: add markers to bot comments and convert cache format.

    Args:
        comments: List of comment dicts
        commits_data: List of commit dicts from PullRequestCommits endpoint
        pr_files_data: List of file dicts from PullRequestFiles endpoint (has real blob SHAs)
    """
    # Build comment_id -> comment dict for first_line lookup during cache conversion
    all_comments: Dict[int, Dict[str, Any]] = {}
    for comment in comments:
        comment_id = comment.get("id")
        if comment_id is not None:
            all_comments[int(comment_id)] = comment

    processed = []
    for comment in comments:
        # First check if it's a cache comment
        body = comment.get("body", "")
        if CMSBOT_TECHNICAL_MSG in body:
            comment = convert_cache_comment(comment, commits_data, all_comments, pr_files_data)
        elif is_bot_comment(comment):
            comment = add_bot_comment_marker(comment)
        processed.append(comment)
    return processed


def convert_to_test_data(records: List[Dict[str, Any]], test_name: str) -> Dict[str, Dict]:
    """
    Convert parsed records to test data format organized by endpoint.

    Returns dict mapping filename to data.
    """
    files = {}

    # First pass: collect commits data and PR files data for cache conversion
    # These may be paginated, so we need to collect all pages
    commits_data = []
    pr_files_data = []
    for record in records:
        if record["status_code"] != 200:
            continue
        path = record["path"]
        endpoint_type, identifier, number = extract_endpoint_info(path)
        if endpoint_type in ("PullRequestCommits", "RepoIdPullRequestCommits"):
            body = parse_response_body(record["response_body"])
            if isinstance(body, list):
                commits_data.extend(body)
        elif endpoint_type in ("PullRequestFiles", "RepoIdPullRequestFiles"):
            body = parse_response_body(record["response_body"])
            if isinstance(body, list):
                pr_files_data.extend(body)

    # Track which paginated endpoints we've seen to merge them
    paginated_data: Dict[str, List] = {}

    # Second pass: convert all endpoints
    for record in records:
        if record["status_code"] != 200:
            # Skip error responses for now
            continue

        path = record["path"]
        endpoint_type, identifier, number = extract_endpoint_info(path)

        if endpoint_type == "Unknown":
            print(f"Warning: Unknown endpoint: {path}", file=sys.stderr)
            continue

        # Skip rate limit - not needed for tests
        if endpoint_type == "RateLimit":
            continue

        body = parse_response_body(record["response_body"])
        if body is None:
            continue

        # Determine filename based on endpoint type and identifiers
        if endpoint_type in ("CommitCombinedStatus", "GitCommit", "Commit", "CommitStatus"):
            # Use SHA as identifier
            filename = f"{endpoint_type}_{identifier}_{number}.json"
        elif endpoint_type == "CommentReactions":
            # Use comment ID
            filename = f"{endpoint_type}_{number}.json"
        elif endpoint_type == "Compare":
            # Use sanitized compare range (replace ... with _)
            safe_range = str(number).replace("...", "_to_")[:40]  # Truncate long SHAs
            filename = f"{endpoint_type}_{identifier}_{safe_range}.json"
        elif endpoint_type == "Milestone":
            filename = f"{endpoint_type}_{identifier}_{number}.json"
        elif endpoint_type == "RepoIdPullRequestFiles":
            # Repo ID based endpoints - normalize to regular endpoint filename
            # so pagination pages get merged with page 1
            filename = f"PullRequestFiles_{number}.json"
        elif endpoint_type == "RepoIdPullRequestCommits":
            # Repo ID based endpoints - normalize to regular endpoint filename
            # so pagination pages get merged with page 1
            filename = f"PullRequestCommits_{number}.json"
        elif endpoint_type == "RepoIdCommits":
            # Repo ID commits (paginated) - skip these as they're pagination of existing data
            continue
        elif number is not None:
            filename = f"{endpoint_type}_{number}.json"
        elif identifier:
            filename = f"{endpoint_type}_{identifier}.json"
        else:
            filename = f"{endpoint_type}.json"

        # Handle list responses (paginated)
        if isinstance(body, list):
            # Check if this is a paginated endpoint that should be merged
            # Note: RepoId variants are normalized to regular endpoint names above
            paginated_endpoints = {
                "PullRequestCommits": "commits",
                "RepoIdPullRequestCommits": "commits",
                "PullRequestFiles": "files",
                "RepoIdPullRequestFiles": "files",
                "IssueComments": "comments",
                "IssueLabels": "labels",
                "PullRequestReviews": "reviews",
                "CommentReactions": "reactions",
            }

            if endpoint_type in paginated_endpoints:
                key = paginated_endpoints[endpoint_type]

                # Process comments to add markers and convert cache
                if endpoint_type == "IssueComments":
                    body = process_comments(body, commits_data, pr_files_data)

                # Merge with existing data for this endpoint
                # Using filename as key ensures RepoId pages merge with regular pages
                if filename in paginated_data:
                    paginated_data[filename].extend(body)
                else:
                    paginated_data[filename] = list(body)

                # Store wrapped data (will be overwritten if more pages, final value is used)
                files[filename] = {key: paginated_data[filename]}
                continue

            # Non-paginated list response - just wrap it
            # (This shouldn't happen for known endpoints)

        files[filename] = body

    return files


def write_test_data(files: Dict[str, Dict], output_dir: Path, test_name: str):
    """Write test data files to output directory."""
    test_dir = output_dir / test_name
    test_dir.mkdir(parents=True, exist_ok=True)

    for filename, data in files.items():
        filepath = test_dir / filename
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Wrote: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Convert HTTP recording to test data JSON format")
    parser.add_argument("test_name", type=str, help="Test name (used as subdirectory name)")
    # parser.add_argument("input_file", type=Path, help="Path to recording file")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("ReplayData_integration"),
        help="Output directory (default: ReplayData_integration)",
    )
    # parser.add_argument(
    #     "-n", "--test-name", type=str, required=True, help="Test name (used as subdirectory name)"
    # )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()
    args.input_file = Path(f"ReplayData.old/TestProcessPr.{args.test_name}.txt")

    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # Parse recording
    print(f"Parsing: {args.input_file}")
    records = parse_recording_file(args.input_file)
    print(f"Found {len(records)} records")

    if args.verbose:
        for record in records:
            print(f"  {record['method']} {record['path']} -> {record['status_code']}")

    # Convert to test data
    files = convert_to_test_data(records, args.test_name)
    print(f"Generated {len(files)} test data files")

    # Write files
    write_test_data(files, args.output_dir, args.test_name)

    print("Done!")


if __name__ == "__main__":
    main()
