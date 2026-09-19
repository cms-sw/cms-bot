#!/usr/bin/env python3
"""
Set commit statuses to mimic a desired test state for a PR.

Usage:
    ./set_test_status.py <pr_id> <status> [options]

Examples:
    ./set_test_status.py 12345 pending
    ./set_test_status.py 12345 passed
    ./set_test_status.py 12345 failed
    ./set_test_status.py 12345 passed --flavor nvidia
    ./set_test_status.py 12345 passed --optional
    ./set_test_status.py 12345 passed --repo cms-sw/cmssw --arch el8_amd64_gcc12
"""

import argparse
import sys
from pathlib import Path

try:
    from github import Github
except ImportError:
    print("Error: PyGithub not installed. Run: pip install PyGithub")
    sys.exit(1)


# Default values
DEFAULT_REPO = "iarspider-cmssw/cmssw"
DEFAULT_ARCH = "el8_amd64_gcc13"

# Status context patterns for CMS bot (from screenshot):
# cms/<pr_id>/<arch>/addon
# cms/<pr_id>/<arch>/relvals
# cms/<pr_id>/<arch>/required  (overall status)
# cms/<pr_id>/<arch>/unittest
# cms/unknown/release
CHECKS = ["addon", "relvals", "unittest"]


def load_github_token() -> str:
    """Load GitHub token from ~/.github-token"""
    token_file = Path.home() / ".github-token"
    if not token_file.exists():
        print(f"Error: Token file not found: {token_file}")
        sys.exit(1)

    token = token_file.read_text().strip()
    if not token:
        print(f"Error: Token file is empty: {token_file}")
        sys.exit(1)

    return token


def get_state_and_description(status: str, check: str) -> tuple[str, str]:
    """Get GitHub state and description for a status."""
    if status == "pending":
        return "pending", "Pending"
    elif status == "passed":
        return "success", "Passed"
    elif status == "failed":
        return "error", "Failed"
    else:
        print(f"Error: Invalid status '{status}'. Use: pending, passed, failed")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Set commit statuses to mimic a desired test state for a PR"
    )
    parser.add_argument("pr_id", type=int, help="Pull request number")
    parser.add_argument(
        "status", choices=["pending", "passed", "failed"], help="Desired test status"
    )
    parser.add_argument(
        "--repo", default=DEFAULT_REPO, help=f"Repository (default: {DEFAULT_REPO})"
    )
    parser.add_argument(
        "--arch", default=DEFAULT_ARCH, help=f"Architecture (default: {DEFAULT_ARCH})"
    )
    parser.add_argument("--flavor", help="Optional flavor (e.g., nvidia)")
    parser.add_argument(
        "--optional", action="store_true", help="Use /optional suffix instead of /required"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print what would be done without making changes"
    )

    args = parser.parse_args()

    suffix = "optional" if args.optional else "required"

    # Load token and create GitHub client
    token = load_github_token()
    gh = Github(token)

    # Get repository and PR
    try:
        repo = gh.get_repo(args.repo)
    except Exception as e:
        print(f"Error: Could not access repository '{args.repo}': {e}")
        sys.exit(1)

    try:
        pr = repo.get_pull(args.pr_id)
    except Exception as e:
        print(f"Error: Could not get PR #{args.pr_id}: {e}")
        sys.exit(1)

    # Get head commit
    head_sha = pr.head.sha
    print(f"PR #{args.pr_id} head commit: {head_sha[:8]}")

    try:
        commit = repo.get_commit(head_sha)
    except Exception as e:
        print(f"Error: Could not get commit {head_sha}: {e}")
        sys.exit(1)

    # Build status context prefix
    # Format from screenshot: cms/<pr_id>/<arch>/<check>
    # With flavor: cms/<pr_id>/<flavor>/<arch>/<check>
    if args.flavor:
        prefix = f"cms/{args.pr_id}/{args.flavor}/{args.arch}"
    else:
        prefix = f"cms/{args.pr_id}/{args.arch}"

    # Set statuses for each check
    for check in CHECKS:
        context = f"{prefix}/{check}/{suffix}"
        state, description = get_state_and_description(args.status, check)

        if args.dry_run:
            print(f"[DRY RUN] Would set {context}: {state} - {description}")
        else:
            try:
                commit.create_status(state=state, description=description, context=context)
                print(f"Set {context}: {state}")
            except Exception as e:
                print(f"Error setting {context}: {e}")

    # Set the overall required/optional status
    overall_context = f"{prefix}/{suffix}"
    if args.status == "pending":
        overall_state, overall_desc = "pending", "Pending"
    elif args.status == "passed":
        overall_state, overall_desc = "success", "OK"
    else:
        overall_state, overall_desc = "error", "Failed"

    if args.dry_run:
        print(f"[DRY RUN] Would set {overall_context}: {overall_state} - {overall_desc}")
    else:
        try:
            commit.create_status(
                state=overall_state, description=overall_desc, context=overall_context
            )
            print(f"Set {overall_context}: {overall_state}")
        except Exception as e:
            print(f"Error setting {overall_context}: {e}")
    #
    # # Set the jenkins status
    # jenkins_context = f"bot/{args.pr_id}/jenkins"
    # if args.status == "pending":
    #     jenkins_state = "pending"
    #     jenkins_desc = "Tests pending"
    # elif args.status == "passed":
    #     jenkins_state = "success"
    #     jenkins_desc = f"Tests requested by user at 2025-01-01 00:00:00 UTC."
    # else:
    #     jenkins_state = "error"
    #     jenkins_desc = "Tests failed"
    #
    # if args.dry_run:
    #     print(f"[DRY RUN] Would set {jenkins_context}: {jenkins_state} - {jenkins_desc}")
    # else:
    #     try:
    #         commit.create_status(
    #             state=jenkins_state, description=jenkins_desc, context=jenkins_context
    #         )
    #         print(f"Set {jenkins_context}: {jenkins_state}")
    #     except Exception as e:
    #         print(f"Error setting {jenkins_context}: {e}")

    print("Done!")


if __name__ == "__main__":
    main()
