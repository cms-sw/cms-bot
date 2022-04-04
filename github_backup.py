#!/usr/bin/env python3
from sys import exit,argv
from os import environ
from os.path import exists, join
from json import load, dump
from time import time, sleep, gmtime
from subprocess import getstatusoutput
from hashlib import md5
import threading
from github_utils import get_organization_repositores, get_repository_issues, check_rate_limits, github_time, get_issue_comments, get_page_range, get_gh_token
from github_utils import get_releases
get_gh_token(token_file=argv[1])
backup_store = argv[2]
if not exists(backup_store):
  print("Backup store not exists.")
  exit(1)

def download_patch(issue, pfile, force=False):
  if 'pull_request' in issue:
    if (not exists(pfile)) or force:
      e, o = getstatusoutput('curl -L -s "%s" > %s.tmp && mv %s.tmp %s' % (issue['pull_request']['patch_url'], pfile, pfile, pfile))
      if e:
        print("ERROR:",issue['number'],o)
        return False
  return True


def process_issue(repo, issue, data):
  num = issue['number']
  pr_md5 = md5((str(num)+"\n").encode()).hexdigest()
  pr_md5_dir = join(backup_store, repo_name, "issues", pr_md5[:2],  pr_md5[2:])
  ifile = join(pr_md5_dir, "issue.json")
  pfile = join(pr_md5_dir, "patch.txt")
  getstatusoutput("mkdir -p %s" % pr_md5_dir)
  status = download_patch(issue, pfile)
  if exists (ifile):
    obj = {}
    with open(ifile) as ref:
      obj = load(ref)
    if obj['updated_at']==issue['updated_at']:
      data['status'] = status
      return
  status = status and download_patch(issue, pfile, True)
  comments = get_issue_comments(repo, num)
  dump(comments, open(join(pr_md5_dir, "comments.json"),"w"))
  dump(issue, open(ifile, "w"))
  print("  Updated ",repo,num,issue['updated_at'],status)
  data['status'] = status
  return

def process_issues(repo, max_threads=8):
  issues = get_repository_issues(repo_name)
  pages = get_page_range()
  check_rate_limits(msg=True)
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
      idate = github_time(issue['updated_at'])
      if latest_date==0: latest_date = idate
      if idate<ref_date:
        pages = []
        break
      check_rate_limits(msg=False, when_slow=True)
      inum = issue['number']
      print("Processing ",repo,inum)
      while (len(threads) >= max_threads):
        sleep(0.01)
        athreads = []
        for t in threads:
          if t[0].is_alive(): athreads.append(t)
          else:
            all_ok = (all_ok and t[1]['status'])
        threads = athreads
      data={'status': False, 'number': inum}
      t = threading.Thread(target=process_issue, args=(repo, issue, data))
      t.start()
      threads.append((t, data))
      sleep(0.01)
    issues = get_repository_issues(repo_name, page = pages.pop(0)) if pages else []
  for t in threads:
    t[0].join()
    all_ok = (all_ok and t[1]['status'])
  if all_ok and (latest_date!=ref_date):
    with open(ref_datefile, "w") as ref:
      ref.write(str(latest_date))
  return

def process_release(repo, rel, data):
  rdir = join(backup_store, repo, "releases", data['year'])
  getstatusoutput("mkdir -p %s" % rdir)
  dump(rel, open(join(rdir, "%s.json" % rel['id']),"w"))
  data['status'] = True
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
      idate = github_time(rels[0]['published_at'])
      if latest_date==0: latest_date = idate
      if idate<ref_date:
        pages = []
        break
      print("Processing release",rel['name'])
      while (len(threads) >= max_threads):
        athreads = []
        for t in threads:
          if t[0].is_alive(): athreads.append(t)
          else:
            all_ok = (all_ok and t[1]['status'])
        threads = athreads
      data={'status': False, 'year': str(gmtime(idate).tm_year) }
      t = threading.Thread(target=process_release, args=(repo, rel, data))
      t.start()
      threads.append((t, data))
    rels = get_releases(repo_name, page=pages.pop(0)) if pages else []
    check_rate_limits(msg=False, when_slow=True)
  for t in threads:
    t[0].join()
    all_ok = (all_ok and t[1]['status'])
  if all_ok and (latest_date!=ref_date):
    with open(ref_datefile, "w") as ref:
      ref.write(str(latest_date))
  return

 
orgs=["cms-sw", "dmwm", "cms-externals", "cms-data", "cms-analysis"]
#no_issues_orgs = ["cms-cvs-history", "cms-obsolete"]
no_issues_orgs = []
orgs += no_issues_orgs
err=0
for org in orgs:
  for repo in get_organization_repositores(org):
    repo_name = repo['full_name']
    print("Working on",repo_name)
    repo_dir = join(backup_store,repo_name)
    repo_stat = join(repo_dir, "json")
    backup = True
    if exists(repo_stat):
      repo_obj = load(open(repo_stat))
      backup = False 
      for v in ['pushed_at', 'pushed_at']:
        if repo_obj[v] != repo[v]:
          backup = True
          break
    if org not in no_issues_orgs:
      process_issues(repo_name)
      process_releases(repo_name)
    if not backup:
      print("  Skipping mirror, no change")
      continue
    getstatusoutput("mkdir -p %s/issues" % repo_dir)
    brepo = join(backup_store, repo_name, "repo")
    if exists(brepo):
      getstatusoutput("mv %s %s.%s" % (brepo, brepo, int(time())))
    getstatusoutput("rm -rf %s.tmp" % brepo)
    e, o = getstatusoutput("git clone --mirror https://github.com/%s %s.tmp" % (repo_name, brepo))
    if e:
      print(o)
      err = 1
    else:
      e, o = getstatusoutput("mv %s.tmp %s" % (brepo, brepo))
      if not e:
        with open(repo_stat, "w") as obj:
          dump(repo, obj)
        print("  Backed up",repo_name)
      else:
        print(o)
        err = 1
exit(err)

