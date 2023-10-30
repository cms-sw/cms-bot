#!/usr/bin/env python
from __future__ import print_function
from github import Github, GithubException
from sys import exit
from os.path import expanduser
from argparse import ArgumentParser
from cms_static import GH_CMSSW_ORGANIZATION
from cms_static import GH_CMSSW_REPO
from _py2with3compatibility import run_cmd

CMSSW_GIT_REF = "/cvmfs/cms.cern.ch/cmssw.git.daily"


def backport_pull(repo, pr, branch):
    pr_branch = pr.base.label.split(":")[1]
    print("Source Branch:", pr_branch)
    if pr_branch == branch:
        return "Warning: Can not backport, same branch %s vs %s" % (pr_branch, branch), False
    br = gh_repo.get_branch(branch)
    commits = []
    for c in pr.get_commits().reversed:
        commits.insert(0, "git cherry-pick %s" % c.sha)
    if not commits:
        return "There are no commits to backport", False
    print("Cherry-pick commands:")
    print("  " + "\n  ".join(commits))
    if len(commits) >= 250:
        return (
            "Error: Too many commits in PR %s\nBot can only handle max 250 commits."
            % len(commits),
            False,
        )
    new_branch = "backport-%s-%s" % (branch.replace("/", "_"), pr.number)
    print("New Branch:", new_branch)
    git_ref = ""
    if repo.name == "cmssw":
        git_ref = "--reference " + CMSSW_GIT_REF
    print("GIT REF:", git_ref)
    e, o = run_cmd(
        "rm -rf pr_backport; git clone --branch %s %s git@github.com:%s pr_backport && cd pr_backport && git checkout -b %s"
        % (branch, git_ref, repo.full_name, new_branch)
    )
    if e:
        print(o)
        exit(1)
    e, o = run_cmd("cd pr_backport; %s" % ";".join(commits))
    if e:
        return (
            "Error: Failed to cherry-pick commits. Please backport this PR yourself.\n```"
            + o
            + "\n```",
            False,
        )
    e, o = run_cmd("cd pr_backport; git push origin %s" % new_branch)
    if e:
        print(o)
        exit(1)
    run_cmd("rm -rf pr_backport")
    newBody = "backport of #%s\n\n%s" % (pr.number, pr.body)
    newPR = repo.create_pull(title=pr.title, body=newBody, base=branch, head=new_branch)
    return (
        "Successfully backported PR #%s as #%s for branch %s" % (pr.number, newPR.number, branch),
        True,
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cmssw.",
        type=str,
        default=GH_CMSSW_REPO,
    )
    parser.add_argument(
        "-b",
        "--branch",
        dest="branch",
        help="Repository branch for which new Pull request should be created.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-p",
        "--pull",
        dest="pull",
        help="Pull request number to be backported.",
        type=int,
        default=0,
    )
    args = parser.parse_args()

    if args.pull == 0:
        parser.error("Missing pull request number.")
    if not args.branch:
        parser.error("Missing branch name.")

    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    gh_repo = gh.get_repo(GH_CMSSW_ORGANIZATION + "/" + args.repository)
    pr = gh_repo.get_pull(args.pull)
    res = backport_pull(gh_repo, pr, args.branch)
    status = "done"
    if not res[1]:
        status = "failed\n**Reason:**\n"
    print(res)
    pr.create_issue_comment("backport %s\n%s" % (status, res[0]))
