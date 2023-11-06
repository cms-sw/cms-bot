#!/usr/bin/env python
from __future__ import print_function
from argparse import ArgumentParser
from github import Github
from os.path import expanduser
from sys import exit
from socket import setdefaulttimeout

setdefaulttimeout(120)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("pr", type=int)
    parser.add_argument("-m", dest="message", type=str, default=None)
    args = parser.parse_args()

    gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
    try:
        pr = gh.get_repo("cms-sw/cmssw").get_pull(args.pr)
    except:
        print("Could not find pull request. Maybe this is an issue?")
        exit(0)
    print(pr.number, ":", pr.title)
    if pr.is_merged():
        print("Pull request is already merged.")
        exit(0)

    if args.message:
        pr.merge(commit_message=message)
    else:
        pr.merge()
