#!/usr/bin/env python
from __future__ import print_function
from os.path import dirname, abspath
from optparse import OptionParser
import sys, re

sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

CMS_BOT_DIR = dirname(dirname(abspath(sys.argv[0])))


def check_commits_files(repo, pr, detail=False):
    status_map = {
        "A": "Added",
        "C": "Copied",
        "D": "Deleted",
        "M": "Modified",
        "R": "Renamed",
        "T": "Type",
        "U": "Unmerged",
        "X": "Unknown",
    }
    invalid_status = [("A", "D"), ("C", "D"), ("R", "D"), ("X", "X"), ("U", "U")]

    all_ok = False
    e, o = run_cmd("%s/process-pull-request -a -c -r %s %s" % (CMS_BOT_DIR, repo, pr))
    if e:
        print(o)
        return all_ok
    details = {}
    data = {}
    for c in o.split("\n"):
        e, o = run_cmd("git diff-tree --no-commit-id --name-status -r %s" % c)
        if e:
            print(o)
            return all_ok
        for l in [re.sub("\s+", " ", x.strip()) for x in o.split("\n") if x.strip()]:
            (t, f) = l.split(" ")
            if not f in data:
                data[f] = []
                details[f] = {}
            if not t in data[f]:
                data[f].append(t)
                details[f][t] = []
            details[f][t].append(c)
    all_ok = True
    for f in data:
        for s in invalid_status:
            if len([1 for x in s if x in data[f]]) > 1:
                if not detail:
                    print("%s: %s" % (f, ", ".join([status_map[x] for x in data[f]])))
                if detail:
                    print("%s:" % f)
                    for x in data[f]:
                        print("  %s: %s" % (status_map[x], ", ".join(details[f][x])))
                all_ok = False
    return all_ok


def process(repo, pr, detail=False):
    if not check_commits_files(repo, pr, detail):
        return False
    return True


if __name__ == "__main__":
    parser = OptionParser(usage="%prog <pull-request-id>")
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-d",
        "--detail",
        dest="detail",
        action="store_true",
        help="Print detail output",
        default=False,
    )
    opts, args = parser.parse_args()

    if len(args) != 1:
        parser.error("Too many/few arguments")
    if not process(opts.repository, args[0], opts.detail):
        sys.exit(1)
