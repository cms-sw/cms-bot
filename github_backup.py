#!/usr/bin/env python3
from sys import exit,argv
from os import environ
from os.path import exists, join
from json import load, dump
from time import time
from subprocess import getstatusoutput
from github_utils import get_organization_repositores, get_repository
token = open(argv[1]).read().strip()
backup_store = argv[2]
if not exists(backup_store):
  print("Backup store not exists.")
  sys.exit(1)
orgs=["cms-sw", "dmwm", "cms-externals", "cms-data", "cms-analysis", "cms-cvs-history", "cms-obsolete"]
err=0
for org in orgs:
  for repo in get_organization_repositores(token, org):
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
    if not backup:
      print("  Skipping, no change")
      continue
    getstatusoutput("mkdir -p %s" % repo_dir)
    brepo = join(backup_store,repo_name, "repo")
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
