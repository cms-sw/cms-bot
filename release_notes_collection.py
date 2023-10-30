#!/usr/bin/env python3
from optparse import OptionParser
import json
import re
from github_utils import github_api, get_gh_token
from collections import namedtuple
from os.path import expanduser, join, exists
from hashlib import md5
import time

RX_RELEASE = re.compile("CMSSW_(\d+)_(\d+)_(\d+)(_pre[0-9]+)*(_cand[0-9]+)*(_patch[0-9]+)*")
RX_AUTHOR = re.compile("(.*)(@[a-zA-Z-_0-9]+)")
RX_COMPARE = re.compile("(https://github.*compare.*\.\.\..*)")
RX_COMMIT = re.compile("^-\s+(:arrow_right:\s*|)([^/]+\/[^/]+|)\#(\d{0,5})( from.*)")

Release = namedtuple(
    "Release", ["major", "minor", "subminor", "pre", "cand", "patch", "published_at"]
)

DEBUG = True


def head(title, release):
    rel_link = title.replace("CMSSW_", "")
    ret = "---\n"
    ret += "layout: post\n"
    ret += 'rel_link:  "{rel_link}"\n'.format(rel_link=rel_link)
    ret += 'title:  "{title}"\n'.format(title=title)
    ret += "date:   {published_at}\n".format(
        published_at=time.strftime(
            "%Y-%m-%d %H:%M:%S", time.strptime(release.published_at, "%Y-%m-%dT%H:%M:%SZ")
        )
    )
    ret += "categories: cmssw\n"
    ret += "relmajor: {major}\n".format(major=release.major)
    ret += "relminor: {minor}\n".format(minor=release.minor)
    ret += "relsubminor: {subminor}\n".format(subminor=release.subminor)
    if release.pre:
        ret += "relpre: {pre}\n".format(pre=release.pre)
    if release.cand:
        ret += "relcand: {cand}\n".format(cand=release.cand)
    if release.patch:
        ret += "relpatch: {patch}\n".format(patch=release.patch)
    ret += "---\n\n"
    return ret


def get_pr(pr, repo, cmsprs):
    pr_md5 = md5((pr + "\n").encode()).hexdigest()
    pr_cache = join(cmsprs, repo, pr_md5[0:2], pr_md5[2:] + ".json")
    if exists(pr_cache):
        return json.load(open(pr_cache))
    return {}


def getReleasesNotes(opts):
    get_gh_token(token_file=expanduser("~/.github-token-cmsbot"))
    notes = []
    error_releases = {}
    print("Reading releases page")
    rel_opt = ""
    if opts.release:
        rel_opt = "/tags/%s" % opts.release
    releases = github_api("/repos/%s/releases%s" % (opts.repository, rel_opt), method="GET")
    if opts.release:
        releases = [releases]
    for release in releases:
        rel_name = release["name"]
        rel_id = str(release["id"])
        print("Checking release", rel_name)
        if " " in rel_name:
            error_releases[rel_name] = "Space in name:" + rel_id
            print("  Skipping release (contains space in name):", rel_name)
            continue
        rel_cyc = "_".join(rel_name.split("_")[0:2])
        rel_numbers = re.match(RX_RELEASE, rel_name)
        if not rel_numbers:
            error_releases[rel_name] = "Does not match release regexp:" + rel_id
            print("  Skipping release (does not match release regexp):", rel_name)
            continue
        if (not "body" in release) or (not release["body"]):
            error_releases[rel_name] = "Empty release body message:" + rel_id
            print("  Skipping release (empty release body message):", rel_name)
            continue
        if not re.match("^%s$" % opts.release_filter, rel_name):
            print("  Skipping release (release does not match filter):", rel_name)
            continue
        rel_file = join(opts.release_notes_dir, rel_cyc, "%s.md" % rel_name)
        if (not opts.force) and exists(rel_file):
            print("  Skipping release (already exists):", rel_name)
            continue
        release_notes = []
        prepo = ""
        count = 0
        forward_port_sym = '<span class="glyphicon glyphicon-arrow-right"></span>'
        for line in release["body"].encode("ascii", "ignore").decode().split("\n"):
            line = re.sub(RX_AUTHOR, "\\1**\\2**", line)
            m = RX_COMMIT.match(line)
            if m:
                repo = opts.repository
                forward_port = ""
                if m.group(1):
                    forward_port = forward_port_sym
                if m.group(2):
                    repo = m.group(2)
                if repo != prepo:
                    count = 0
                prepo = repo
                count += 1
                line = (
                    "\n{count}. {forward_port}[{pr}](http://github.com/{repo}/pull/{pr})".format(
                        forward_port=forward_port, count=count, repo=repo, pr=m.group(3)
                    )
                    + '{:target="_blank"} '
                    + m.group(4)
                )
                pr = get_pr(m.group(3), repo, opts.prs_dir)
                print("  PR found: " + repo + "#" + m.group(3))
                if "created_at" in pr:
                    line += " created: " + time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(float(pr["created_at"]))
                    )
                if "merged_at" in pr:
                    line += " merged: " + time.strftime(
                        "%Y-%m-%d %H:%M:%S", time.localtime(float(pr["merged_at"]))
                    )
            elif RX_COMPARE.match(line):
                line = re.sub(RX_COMPARE, "[compare to previous](\\1)\n\n", line)

            release_notes.append(line.replace(":arrow_right:", forward_port_sym))
        r = Release(
            int(rel_numbers.group(1)),
            int(rel_numbers.group(2)),
            int(rel_numbers.group(3)),
            rel_numbers.group(4),
            rel_numbers.group(5),
            rel_numbers.group(6),
            release["published_at"],
        )
        out_rel = open(rel_file, "w")
        out_rel.write(head(rel_name, r))
        out_rel.write("# %s\n%s" % (rel_name, "\n".join(release_notes)))
        out_rel.close()
        print("  Created release notes:", rel_name)
    if error_releases:
        print("Releases with errors:", error_releases)


if __name__ == "__main__":
    parser = OptionParser(usage="%prog")
    parser.add_option(
        "-r",
        "--repository",
        dest="repository",
        help="Github Repositoy name e.g. cms-sw/cmssw.",
        type=str,
        default="cms-sw/cmssw",
    )
    parser.add_option(
        "-p",
        "--prs-path",
        dest="prs_dir",
        help="Directory with Pull request",
        type=str,
        default="cms-prs",
    )
    parser.add_option(
        "-N",
        "--release-notes",
        dest="release_notes_dir",
        help="Directory where to store release notes",
        type=str,
        default="ReleaseNotes/_releases",
    )
    parser.add_option(
        "-R", "--release", dest="release", help="Release name", type=str, default=None
    )
    parser.add_option(
        "-F",
        "--release-filter",
        dest="release_filter",
        help="Release filter",
        type=str,
        default="CMSSW_.*",
    )
    parser.add_option(
        "-f",
        "--force",
        dest="force",
        action="store_true",
        help="Force re-creation of release notes",
        default=False,
    )
    opts, args = parser.parse_args()
    if opts.release:
        opts.force = True
    getReleasesNotes(opts)
