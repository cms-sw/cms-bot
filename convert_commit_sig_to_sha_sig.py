import argparse
import copy
import datetime
import logging
import re
from os.path import join, dirname, abspath, exists
from pprint import pprint
from types import ModuleType
from typing import Optional

from github import Github
from github.Issue import Issue
from github.IssueComment import IssueComment
from github.Repository import Repository

import process_pr
from cms_static import ISSUE_SEEN_MSG, CMSBOT_TECHNICAL_MSG
from github_utils import get_gh_token, api_rate_limits

logger = None


def ensure_ascii(string: str) -> str:
    return string.encode("ascii", "ignore").decode("ascii", "ignore")


def convert(
    repo_config: ModuleType,
    gh: Github,
    repo: Repository,
    issue: Issue,
    bot_cache: dict,
    comments: list[IssueComment],
):
    """
    One-shot migration to a commit-free, incremental schema:

      bot_cache = {
          "fv": {
              "path::blob": { "ts": "<UTC-ISO>", "cats": ["..."] },
              ...
          },
          "comments": {
              "<comment_id>": {
                  "ts": "<UTC-ISO>",
                  "first_line": "<parsed>",
                  "ctype": "+1" | "-1",
                  "cats": ["..."],
                  "fv": ["path::blob", ...]
              },
              ...
          }
      }

    Notes:
    - No commit ids are persisted.
    - 'ts' on fv = timestamp of the commit that introduced that blob (first time we saw it).
    - 'cats' on fv are frozen at that blob.
    - Per-file signature rollups are NOT stored; rebuild on demand from (fv + comments).
    """
    import datetime as _dt
    import re

    def _iso_utc(dt) -> str:
        # Normalize naive/aware to ISO UTC Z
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.timezone.utc)
        else:
            dt = dt.astimezone(_dt.timezone.utc)
        return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # Legacy input: comment_id -> commit_sha
    legacy_signatures: dict = bot_cache.get("signatures", {})

    # New sections
    fv_section = bot_cache.setdefault("fv", {})
    new_comments = bot_cache.setdefault("comments", {})

    # Local caches (not persisted)
    comments_by_id = {c.id: c for c in comments}
    blob_cache: dict[tuple[str, str], Optional[str]] = {}  # (commit, path) -> blob sha
    commit_ts_cache: dict[str, str] = {}  # commit -> ISO ts
    commit_files_cache: dict[str, list[str]] = {}  # commit -> [paths]
    path_cats_mem: dict[str, list[str]] = {}  # path -> cats

    def _cats_for_path(path: str, repo_config: ModuleType) -> list[str]:
        # file -> single package -> categories; memoized in-memory only
        if path in path_cats_mem:
            return path_cats_mem[path]
        try:
            pkg = process_pr.cmssw_file2Package(repo_config, path)
            cats = list(process_pr.get_package_categories(pkg)) if pkg else []
        except Exception:
            cats = []
        path_cats_mem[path] = cats
        return cats

    for comment_id, commit_sha in legacy_signatures.items():
        cid_int = int(comment_id)
        cid_str = str(comment_id)
        cobj = comments_by_id.get(cid_int)
        if cobj is None:
            logger.error(
                "Comment id %s (%s#issuecomment-%s) missing; skipping.",
                cid_int,
                issue.html_url,
                cid_int,
            )
            continue

        # --- commit timestamp + files (API once per commit) ---
        if commit_sha not in commit_ts_cache:
            try:
                gh_commit = repo.get_commit(commit_sha)
                commit_dt = gh_commit.commit.committer.date
                commit_ts_iso = _iso_utc(commit_dt)
                commit_paths = [f.filename for f in gh_commit.files]
            except Exception as e:
                logger.error("Failed to fetch commit %s", commit_sha, exc_info=e)
                continue
            commit_ts_cache[commit_sha] = commit_ts_iso
            commit_files_cache[commit_sha] = commit_paths

        commit_ts_iso = commit_ts_cache[commit_sha]
        commit_paths = commit_files_cache[commit_sha]

        # --- parse first non-empty line & commenter categories at comment time ---
        first_line = next((ln.strip() for ln in (cobj.body or "").splitlines() if ln.strip()), "")
        try:
            comment_ts_iso = _iso_utc(cobj.created_at)
            comment_ts_int = int(cobj.created_at.replace(tzinfo=_dt.timezone.utc).timestamp())
        except Exception:
            now = _dt.datetime.now(_dt.timezone.utc)
            comment_ts_iso = _iso_utc(now)
            comment_ts_int = int(now.timestamp())

        commenter_login = ensure_ascii(cobj.user.login)
        try:
            commenter_categories = process_pr.get_commenter_categories(
                commenter_login, comment_ts_int
            )
        except Exception as e:
            logger.error(
                "Category lookup failed for %s at %s", commenter_login, comment_ts_int, exc_info=e
            )
            continue

        ctype = "0"
        selected_cats: list[str] = []
        if first_line:
            if re.fullmatch(r"\+1|approved?|sign(?:ed)?", first_line, re.I):
                ctype = "+1"
                selected_cats = commenter_categories[:]
            elif re.fullmatch(r"-1|reject(?:ed)?", first_line, re.I):
                ctype = "-1"
                selected_cats = commenter_categories[:]
            elif re.fullmatch(r"[+-][a-z][a-z0-9-]+", first_line, re.I):
                cat_name = first_line[1:].lower()
                if cat_name in commenter_categories:
                    ctype = first_line[0] + "1"
                    selected_cats = [cat_name]
        if ctype == "0" or not selected_cats:
            # not an approval-ish command — skip in conversion
            continue

        # --- resolve file-versions for this commit & register them (with first-seen ts + cats) ---
        fv_keys_for_comment: list[str] = []

        for path in commit_paths:
            key = (commit_sha, path)
            if key in blob_cache:
                blob_sha = blob_cache[key]
            else:
                try:
                    contents = repo.get_contents(path, ref=commit_sha)
                    blob_sha = contents.sha
                except Exception:
                    blob_sha = None
                blob_cache[key] = blob_sha

            fv_key = f"{path}::{blob_sha}" if blob_sha else path

            # Ensure fv entry exists with frozen cats-at-blob
            if fv_key not in fv_section:
                fv_section[fv_key] = {
                    "ts": commit_ts_iso,  # first seen = commit timestamp
                    "cats": _cats_for_path(
                        path, repo_config
                    ),  # <- snapshot categories for this blob
                }
            else:
                fv_section[fv_key].setdefault("cats", _cats_for_path(path, repo_config))

            # ONLY include this fv if its cats intersect the comment's cats
            fv_cats = set(fv_section[fv_key].get("cats", []))
            if fv_cats & set(selected_cats):
                fv_keys_for_comment.append(fv_key)

        # Then store the comment with the filtered fv list:
        new_comments[cid_str] = {
            "ts": comment_ts_iso,
            "first_line": first_line,
            "ctype": ctype,
            "cats": selected_cats,
            "fv": fv_keys_for_comment,  # filtered by category overlap
        }

    # Drop legacy sections; keep only emoji + fv + comments
    bot_cache.pop("signatures", None)
    bot_cache.pop("commits", None)
    bot_cache.pop("last_seen_sha", None)

    return bot_cache


def _fv_key(path, blob):
    return f"{path}::{blob}" if blob else path


def _cats_for_path(path):
    try:
        pkg = process_pr.cmssw_file2Package(repo_config, path)
        return list(process_pr.get_package_categories(pkg)) if pkg else []
    except Exception:
        return []


def _get_blob_sha(repo, path, ref):
    try:
        return repo.get_contents(path, ref=ref).sha
    except Exception:
        return None


def _iter_pr_files(pr):
    head_sha, base_sha = pr.head.sha, pr.base.sha
    for f in pr.get_files():
        st = getattr(f, "status", None)
        path_new = f.filename
        prev = getattr(f, "previous_filename", None)
        if st == "removed":
            yield {"path": path_new, "ref": base_sha}
        elif st == "renamed":
            if prev:
                yield {"path": prev, "ref": base_sha}
            yield {"path": path_new, "ref": head_sha}
        else:
            yield {"path": path_new, "ref": head_sha}


def _per_fv_sign(cache, fv_key, cat):
    comments = sorted(cache.get("comments", {}).values(), key=lambda c: c.get("ts", ""))
    state = 0
    for c in comments:
        if cat not in c.get("cats", ()):
            continue
        if fv_key not in c.get("fv", ()):
            continue
        if c.get("ctype") == "+1":
            state = +1
        elif c.get("ctype") == "-1":
            state = -1
    return state


def compute_signatures_for_issue(repo, pr, cache, repo_config):
    """
    Given a GitHub Issue (already known to be a PR), compute overall signature
    states for all categories affected by that PR.

    Returns a flat list like:
        ["foo-approved", "bar-rejected", "baz-pending", "bat-approved"]

    Meaning:
        +1  →  "<cat>-approved"
        -1  →  "<cat>-rejected"
         0  →  "<cat>-pending"

    Rules:
      • Each category is evaluated independently.
      • A category is "approved" if *all* relevant file-versions (fvs)
        for that category are signed +1.
      • It is "rejected" if *any* fv is signed −1.
      • It is "pending" if none are rejected but at least one fv is unsigned.
      • “Relevant fvs” = union of:
          – HEAD-side fvs for added/modified/renamed files
          – BASE-side fvs for removed/renamed files
    """
    # --- main logic ----------------------------------------------------------

    # 1) collect fvs per category
    cat_to_fvs = {}
    seen = set()
    for item in _iter_pr_files(pr):
        path, ref = item["path"], item["ref"]
        blob = _get_blob_sha(repo, path, ref)
        fv_key = _fv_key(path, blob)
        if fv_key in seen:
            continue
        seen.add(fv_key)
        cats = cache.get("fv", {}).get(fv_key, {}).get("cats") or _cats_for_path(path)
        for cat in cats:
            cat_to_fvs.setdefault(cat, set()).add(fv_key)

    # 2) Evaluate each category with priority pending > rejected > approved
    out: list[str] = []
    for cat, fvs in sorted(cat_to_fvs.items()):
        # compute per-fv states
        states = [_per_fv_sign(cache, fv, cat) for fv in fvs]
        if any(s == 0 for s in states):
            out.append(f"{cat}-pending")
        elif any(s < 0 for s in states):
            out.append(f"{cat}-rejected")
        else:
            out.append(f"{cat}-approved")

    return out


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repository", default="cms-sw/cmssw")
    parser.add_argument("prid", type=int)

    args = parser.parse_args(args)

    print("Setting up")
    import sys

    SCRIPT_DIR = dirname(abspath(sys.argv[0]))

    repo_dir = join(SCRIPT_DIR, "repos", args.repository.replace("-", "_"))
    if exists(repo_dir):
        sys.path.insert(0, repo_dir)
    import repo_config

    gh = Github(login_or_token=get_gh_token(args.repository), per_page=100)
    api_rate_limits(gh)
    repo: Repository = gh.get_repo(args.repository)
    issue: Issue = repo.get_issue(args.prid)

    if not issue.pull_request:
        raise RuntimeError(f"Issue {args.repository}#{args.prid} is not a PR")

    repository = repo.full_name
    repo_org, repo_name = repository.split("/", 1)

    from categories import EXTERNAL_REPOS
    from categories import CMSSW_CATEGORIES as default_CMSSW_CATEGORIES

    cms_repo = repo_org in EXTERNAL_REPOS
    process_pr.L2_DATA = process_pr.init_l2_data(repo_config, cms_repo)

    CMSSW_CATEGORIES = copy.deepcopy(default_CMSSW_CATEGORIES)

    # LEGACY_CATEGORIES is a mapping from name to datetime (when the category becomes legacy)
    # Extract categories that are legacy at the moment of issue creation
    legacy_cats = getattr(repo_config, "LEGACY_CATEGORIES", {})
    issue_created_at: datetime.datetime = issue.created_at
    if issue_created_at.tzinfo is None:
        issue_created_at = issue_created_at.replace(tzinfo=datetime.timezone.utc)

    for lc in (cat for cat, ts in legacy_cats.items() if issue_created_at > ts):
        logger.info("Removing legacy category %s from CMSSW_CATEGORIES", lc)
        del CMSSW_CATEGORIES[lc]

    process_pr.CMSSW_CATEGORIES = CMSSW_CATEGORIES

    all_comments: list[IssueComment] = []
    technical_comments: list[IssueComment] = []
    comment: IssueComment
    already_seen: Optional[IssueComment] = None
    cmsbuild_user = repo_config.CMSBUILD_USER

    print("Looking for bot cache")

    for comment in issue.get_comments():
        all_comments.append(comment)
        if ensure_ascii(comment.user.login) != cmsbuild_user:
            continue
        comment_msg = ensure_ascii(comment.body) if comment.body else ""
        first_line = "".join([l.strip() for l in comment_msg.split("\n") if l.strip()][0:1])
        if (not already_seen) and re.match(ISSUE_SEEN_MSG, first_line):
            already_seen = comment
            if process_pr.REGEX_COMMITS_CACHE.search(comment_msg):
                technical_comments.append(comment)
        elif re.match(CMSBOT_TECHNICAL_MSG, first_line):
            technical_comments.append(comment)

    print("Loading bot cache")
    if technical_comments:
        bot_cache = process_pr.extract_bot_cache(technical_comments)
    else:
        raise RuntimeError(f"PR {args.repository}#{args.prid} doesn't have bot cache!")

    # Make sure bot cache has the needed keys
    for k, v in process_pr.BOT_CACHE_TEMPLATE.items():
        if k not in bot_cache:
            bot_cache[k] = copy.deepcopy(v)

    pprint(bot_cache)

    ##############################################################################################
    # End boilerplate code                                                                       #
    ##############################################################################################

    api_rate_limits(gh)
    print("Starting migration")
    new_bot_cache = convert(repo_config, gh, repo, issue, bot_cache, all_comments)
    print("Migration complete!")
    api_rate_limits(gh)
    pprint(bot_cache)

    pr = issue.as_pull_request()

    a = compute_signatures_for_issue(repo, pr, new_bot_cache, repo_config)
    pprint(a)


if __name__ == "__main__":
    process_pr.setup_logging(logging.DEBUG)
    logger = process_pr.logger
    main(["49346"])
