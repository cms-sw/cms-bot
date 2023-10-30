#!/usr/bin/env python3
from github import Github
from os.path import expanduser
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument(
    "-r", "--repository", dest="repo", help="Github Repositoy name e.g cms-sw/cms-bot", type=str
)
parser.add_argument(
    "-b",
    "--base_branch",
    dest="base_branch",
    help="Repository branch againt which new Pull request should be created",
    type=str,
)
parser.add_argument(
    "-f",
    "--feature_branch",
    dest="feature_branch",
    help="New feature branch to be merged",
    type=str,
)
parser.add_argument("-t", "--title", dest="title", help="Pull request title", type=str)
parser.add_argument(
    "-d", "--body", dest="body", help="Pull request body text, optional", type=str, default=""
)
parser.add_argument(
    "-c",
    "--comment",
    dest="comment",
    help="Extra comment after creating Pull requests e.g. please tests",
    type=str,
    default="",
)

args = parser.parse_args()
if not args.repo:
    parser.error("Missing Repo")
if not args.base_branch:
    parser.error("Missing base branch name.")
if not args.feature_branch:
    parser.error("Missing feature branch name.")
if not args.title:
    parser.error("Missing PR title")
print("Authenticating to Github and connecting to repo")
gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
print("Authentication succeeeded")
gh_repo = gh.get_repo(args.repo)
print("Creating pull request")
pr = gh_repo.create_pull(
    title=args.title,
    body=args.body.replace("@N@", "\n"),
    base=args.base_branch,
    head=args.feature_branch,
)
if args.comment:
    pr.create_issue_comment(body=args.comment)
