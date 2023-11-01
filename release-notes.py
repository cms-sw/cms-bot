#!/usr/bin/env python3
from optparse import OptionParser
from os.path import exists, expanduser, join
from _py2with3compatibility import run_cmd, Request, urlopen, HTTPError
from github import Github
import json
from sys import exit
import re
from cms_static import GH_CMSSW_REPO, GH_CMSDIST_REPO, GH_CMSSW_ORGANIZATION
from github_utils import prs2relnotes, get_merge_prs, get_release_by_tag
from socket import setdefaulttimeout
from categories import get_dpg_pog

setdefaulttimeout(120)
CMSDIST_REPO_NAME = join(GH_CMSSW_ORGANIZATION, GH_CMSDIST_REPO)
CMSSW_REPO_NAME = join(GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO)


def format(s, **kwds):
    return s % kwds


# ---------------------------------------------------------
# pyGithub
# --------------------------------------------------------


#
# defines the categories for each pr in the release notes
#
def add_categories_notes(notes, cache):
    dpg_pog_labels = get_dpg_pog()
    for pr_number in notes:
        categories = [
            l.split("-")[0]
            for l in cache[pr_number]["pr"]["labels"]
            if (
                re.match("^[a-zA-Z0-9]+[-](approved|pending|hold|rejected)$", l)
                and not re.match("^(tests|orp)-", l)
            )
            or l in dpg_pog_labels
        ]
        if len(categories) == 0:
            print("no categories for:", pr_number)
        else:
            print("Labels for %s: %s" % (pr_number, categories))
        note = notes[pr_number]
        for cat in categories:
            note += " `%s`" % cat

        if "release-notes" in cache[pr_number]["pr"]:
            rel_notes = "\n".join(cache[pr_number]["pr"]["release-notes"])
            note = note + rel_notes
        notes[pr_number] = note
    return notes


def get_cmssw_notes(previous_release, this_release, cache):
    if not exists("cmssw.git"):
        error, out = run_cmd(
            "git clone --bare --reference /cvmfs/cms-ib.cern.ch/git/cms-sw/cmssw.git git@github.com:cms-sw/cmssw.git"
        )
        if error:
            parser.error("Error while checking out the repository:\n" + out)
    run_cmd("GIT_DIR=cmssw.git git fetch --all --tags")
    return prs2relnotes(
        get_merge_prs(previous_release, this_release, "cmssw.git", "cms-prs", cache)
    )


#
# gets the changes in cmsdist, production architecture is the production architecture of the release
#
def get_cmsdist_notes(prev_cmsdist_tag, curr_cmsdist_tag, cache):
    if not exists("cmsdist.git"):
        error, out = run_cmd("git clone --bare git@github.com:cms-sw/cmsdist.git")
        if error:
            parser.error("Error while checking out the cmsdist repository:\n" + out)
    run_cmd("GIT_DIR=cmsdist.git git fetch --all --tags")
    return prs2relnotes(
        get_merge_prs(prev_cmsdist_tag, curr_cmsdist_tag, "cmsdist.git", "cms-prs", cache),
        "cms-sw/cmsdist",
    )


#
# returns the comparison url to include in the notes
#
def get_comparison_url(previous_tag, current_tag, repo):
    return COMPARISON_URL % (repo, previous_tag, current_tag)


# --------------------------------------------------------------------------------
# Start of Execution
# --------------------------------------------------------------------------------

COMPARISON_URL = "https://github.com/cms-sw/%s/compare/%s...%s"

if __name__ == "__main__":
    parser = OptionParser(
        usage="%(progname) <previous-release> <this-release> <previous-cmsdist-tag> <this-cmsdist-tag>"
    )
    parser.add_option(
        "-n",
        "--dry-run",
        help="Only print out release notes. Do not execute.",
        dest="dryRun",
        default=False,
        action="store_true",
    )
    opts, args = parser.parse_args()

    if len(args) != 4:
        parser.error("Wrong number or arguments")
    prev_release = args[0]
    curr_release = args[1]
    prev_cmsdist_tag = args[2]
    curr_cmsdist_tag = args[3]

    # ---------------------------------
    # pyGithub intialization
    # ---------------------------------

    token = open(expanduser("~/.github-token")).read().strip()
    github = Github(login_or_token=token)
    CMSSW_REPO = github.get_repo(CMSSW_REPO_NAME)
    CMSDIST_REPO = github.get_repo(CMSDIST_REPO_NAME)

    if not exists("cms-prs"):
        error, out = run_cmd("git clone --depth 1 git@github.com:cms-sw/cms-prs")
        if error:
            parser.error("Error while checking out cms-sw/cms-prs repository:\n" + out)
    cmssw_cache = {}
    cmsdist_cache = {}
    cmssw_notes = get_cmssw_notes(prev_release, curr_release, cmssw_cache)
    cmsdist_notes = get_cmsdist_notes(prev_cmsdist_tag, curr_cmsdist_tag, cmsdist_cache)

    cmssw_notes = add_categories_notes(cmssw_notes, cmssw_cache)
    cmssw_notes_str = ""
    cmsdist_notes_str = ""
    for pr in sorted(list(cmssw_notes.keys()), reverse=True):
        cmssw_notes_str += cmssw_notes[pr] + "\n"
    for pr in sorted(list(cmsdist_notes.keys()), reverse=True):
        cmsdist_notes_str += cmsdist_notes[pr] + "\n"
    header = "#### Changes since %s:\n%s\n" % (
        prev_release,
        get_comparison_url(prev_release, curr_release, "cmssw"),
    )
    cmsdist_header = "\n#### CMSDIST Changes between Tags %s and %s:\n%s\n" % (
        prev_cmsdist_tag,
        curr_cmsdist_tag,
        get_comparison_url(prev_cmsdist_tag, curr_cmsdist_tag, "cmsdist"),
    )

    try:
        release = get_release_by_tag("cms-sw/cmssw", curr_release)
        url = "https://api.github.com/repos/cms-sw/cmssw/releases/%s" % release["id"]
        if not opts.dryRun:
            request = Request(url, headers={"Authorization": "token " + token})
            request.get_method = lambda: "PATCH"
            print("Modifying release notes for %s at %s" % (curr_release, url))
            print(
                urlopen(
                    request,
                    json.dumps(
                        {"body": header + cmssw_notes_str + cmsdist_header + cmsdist_notes_str}
                    ).encode(),
                ).read()
            )
        else:
            print(header)
            print(cmssw_notes_str)
            print(cmsdist_header)
            print(cmsdist_notes_str)
            print("--dry-run specified, quitting without modifying release.")
        print("ALL_OK")
        exit(0)
    except HTTPError as e:
        print(e)
        print("Release %s not found." % curr_release)
        exit(1)
