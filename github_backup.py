#!/usr/bin/env python3
from sys import exit, argv
from os import environ
from os.path import exists, join, dirname
from json import load, dump
from time import time, sleep, gmtime
from subprocess import getstatusoutput
from hashlib import md5
import threading, re
from github_utils import (
    get_organization_repositores,
    get_repository_issues,
    check_rate_limits,
    github_time,
    get_issue_comments,
    get_page_range,
    get_gh_token,
)
from github_utils import get_releases

get_gh_token(token_file=argv[1])
backup_store = argv[2]
comment_imgs_regexp = re.compile("^(.*?)\!\[[^\]]+\]\(([^\)]+)\)(.*)$")
if not exists(backup_store):
    print("Backup store not exists.")
    exit(1)


def download_patch(issue, pfile, force=False):
    if "pull_request" in issue:
        if (not exists(pfile)) or force:
            e, o = getstatusoutput(
                'curl -L -s "%s" > %s.tmp && mv %s.tmp %s'
                % (issue["pull_request"]["patch_url"], pfile, pfile, pfile)
            )
            if e:
                print("ERROR:", issue["number"], o)
                return 1
    return 0


def process_comment(body, repo):
    err = 0
    if not body:
        return err
    for comment in body.split("\n"):
        while comment:
            m = comment_imgs_regexp.match("  " + comment + "   ")
            if not m:
                break
            comment = "%s%s" % (m.group(1), m.group(3))
            url = m.group(2)
            if ('"' in url) or ("'" in url):
                continue
            if url.startswith("data:"):
                continue
            ifile = "%s/%s/images/%s" % (backup_store, repo, url.split("://")[-1])
            ifile = re.sub("[^a-zA-Z0-9/._-]", "", ifile)
            if exists(ifile):
                continue
            getstatusoutput("mkdir -p %s" % dirname(ifile))
            try:
                cmd = "curl -L -s '%s' > %s.tmp && mv %s.tmp %s" % (url, ifile, ifile, ifile)
                e, o = getstatusoutput(cmd)
                if e:
                    print("    ERROR:", o)
                    err = 1
                else:
                    print("    Download user content: ", url)
            except:
                print("ERROR: Runing ", cmd)
                err = 1
    return err


def process_issue(repo, issue, data):
    num = issue["number"]
    pr_md5 = md5((str(num) + "\n").encode()).hexdigest()
    pr_md5_dir = join(backup_store, repo_name, "issues", pr_md5[:2], pr_md5[2:])
    ifile = join(pr_md5_dir, "issue.json")
    pfile = join(pr_md5_dir, "patch.txt")
    getstatusoutput("mkdir -p %s" % pr_md5_dir)
    err = process_comment(issue["body"], repo)
    err += download_patch(issue, pfile)
    if exists(ifile):
        obj = {}
        with open(ifile) as ref:
            obj = load(ref)
        if obj["updated_at"] == issue["updated_at"]:
            data["status"] = False if err > 0 else True
            return
    err += download_patch(issue, pfile, True)
    comments = get_issue_comments(repo, num)
    for c in comments:
        err += process_comment(c["body"], repo)
    dump(comments, open(join(pr_md5_dir, "comments.json"), "w"))
    dump(issue, open(ifile, "w"))
    print("    Updated ", repo, num, issue["updated_at"], err)
    data["status"] = False if err > 0 else True
    return


def process_issues(repo, max_threads=8):
    issues = get_repository_issues(repo_name)
    pages = get_page_range()
    check_rate_limits(msg=True, prefix="  ")
    threads = []
    all_ok = True
    latest_date = 0
    ref_datefile = join(backup_store, repo, "issues", "latest.txt")
    ref_date = 0
    if exists(ref_datefile):
        with open(ref_datefile) as ref:
            ref_date = int(ref.read().strip())
    while issues:
        for issue in issues:
            idate = github_time(issue["updated_at"])
            if latest_date == 0:
                latest_date = idate
            if idate <= ref_date:
                pages = []
                break
            check_rate_limits(msg=False, when_slow=True, prefix="  ")
            inum = issue["number"]
            print("  Processing ", repo, inum)
            while len(threads) >= max_threads:
                sleep(0.01)
                athreads = []
                for t in threads:
                    if t[0].is_alive():
                        athreads.append(t)
                    else:
                        all_ok = all_ok and t[1]["status"]
                threads = athreads
            data = {"status": False, "number": inum}
            t = threading.Thread(target=process_issue, args=(repo, issue, data))
            t.start()
            threads.append((t, data))
            sleep(0.01)
        issues = get_repository_issues(repo_name, page=pages.pop(0)) if pages else []
    for t in threads:
        t[0].join()
        all_ok = all_ok and t[1]["status"]
    if all_ok and (latest_date != ref_date):
        with open(ref_datefile, "w") as ref:
            ref.write(str(latest_date))
    return


def process_release(repo, rel, data):
    rdir = join(backup_store, repo, "releases", data["year"])
    getstatusoutput("mkdir -p %s" % rdir)
    dump(rel, open(join(rdir, "%s.json" % rel["id"]), "w"))
    data["status"] = True
    return


def process_releases(repo, max_threads=8):
    rels = get_releases(repo_name)
    pages = get_page_range()
    check_rate_limits(msg=True)
    threads = []
    all_ok = True
    latest_date = 0
    ref_datefile = join(backup_store, repo, "releases", "latest.txt")
    ref_date = 0
    if exists(ref_datefile):
        with open(ref_datefile) as ref:
            ref_date = int(ref.read().strip())
    while rels:
        for rel in rels:
            idate = github_time(rel["published_at"])
            if latest_date == 0:
                latest_date = idate
            if idate <= ref_date:
                pages = []
                break
            print("  Processing release", rel["name"])
            while len(threads) >= max_threads:
                athreads = []
                for t in threads:
                    if t[0].is_alive():
                        athreads.append(t)
                    else:
                        all_ok = all_ok and t[1]["status"]
                threads = athreads
            data = {"status": False, "year": str(gmtime(idate).tm_year)}
            t = threading.Thread(target=process_release, args=(repo, rel, data))
            t.start()
            threads.append((t, data))
        rels = get_releases(repo_name, page=pages.pop(0)) if pages else []
        check_rate_limits(msg=False, when_slow=True)
    for t in threads:
        t[0].join()
        all_ok = all_ok and t[1]["status"]
    if all_ok and (latest_date != ref_date):
        with open(ref_datefile, "w") as ref:
            ref.write(str(latest_date))
    return


##########################################################
orgs = {
    "cms-sw": ["issues", "releases"],
    "dmwm": ["issues", "releases"],
    "cms-externals": ["issues"],
    "cms-data": ["issues"],
    "cms-analysis": ["issues", "releases"],
    "cms-cvs-history": [],
    "cms-obsolete": [],
}

err = 0
e, o = getstatusoutput("date")
print("=================================================")
print(o.strip())
print("=================================================")
for org in orgs:
    for repo in get_organization_repositores(org):
        repo_name = repo["full_name"]
        print("Working on", repo_name)
        repo_dir = join(backup_store, repo_name)
        repo_stat = join(repo_dir, "json")
        backup = True
        if exists(repo_stat):
            repo_obj = load(open(repo_stat))
            backup = False
            for v in ["pushed_at", "updated_at"]:
                if repo_obj[v] != repo[v]:
                    backup = True
                    break
        getstatusoutput("mkdir -p %s" % repo_dir)
        if "issues" in orgs[org]:
            print("  Processing issues for", repo_name)
            getstatusoutput("mkdir -p %s/issues" % repo_dir)
            process_issues(repo_name)
        if "releases" in orgs[org]:
            print("  Processing releases for", repo_name)
            getstatusoutput("mkdir -p %s/releases" % repo_dir)
            process_releases(repo_name)
        if not backup:
            print("  Skipping mirror, no change")
            continue
        brepo = join(repo_dir, "repo")
        if exists(brepo):
            getstatusoutput("mv %s %s.%s" % (brepo, brepo, int(time())))
        getstatusoutput("rm -rf %s.tmp" % brepo)
        print("  Mirroring repository", repo_name)
        e, o = getstatusoutput(
            "git clone --mirror https://github.com/%s %s.tmp" % (repo_name, brepo)
        )
        if e:
            print(o)
            err = 1
        else:
            e, o = getstatusoutput("mv %s.tmp %s" % (brepo, brepo))
            if not e:
                with open(repo_stat, "w") as obj:
                    dump(repo, obj)
                print("  Backed up", repo_name)
                getstatusoutput(
                    "find %s -mindepth 1 -maxdepth 1 -name 'repo.*' | sort |  head -n -100 | xargs rm -rf"
                    % repo_dir
                )
            else:
                print(o)
                err = 1
e, o = getstatusoutput("date")
print("=================================================")
print(o.strip())
print("=================================================")
exit(err)
