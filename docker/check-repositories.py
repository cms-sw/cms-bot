#!/usr/bin/env python
from __future__ import print_function
import sys
from os.path import exists, dirname, abspath
import yaml, json
from sys import exit
from optparse import OptionParser
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

def get_repos(user, cache):
  if user not in cache:
    cache[user] = []
    url = 'https://hub.docker.com/v2/repositories/%s?page_size=100' % user
    while True:
      e , o = run_cmd('curl -s -L %s' % url)
      repo_data = json.loads(o)
      if "results" in repo_data:
        for r in repo_data["results"]:
          cache[user].append(r["name"])
      if "next" in repo_data and repo_data["next"]:
        url = repo_data["next"]
      else:
        break
  return cache[user]

def process(repos, dryRun, cache):
  for data in repos:
    for u in data:
      existing_repos = get_repos(u, cache)
      for r in data[u]:
        if r not in existing_repos:
          print("%s/%s NEW" % (u, r))

if __name__ == "__main__":
  parser = OptionParser(usage="%prog <pull-request-id>")
  parser.add_option("-n", "--dry-run",    dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-r", "--repo-list",  dest="repo_list",  help="Yaml file with list of repositories to create under docker hun", type=str, default=None)
  opts, args = parser.parse_args()

  repos = {}
  if not opts.repo_list:
    parser.error("Missing repository list file, please use -r|--repo-list option")
  
  if opts.repo_list.startswith('https://'):
    e, o = run_cmd('curl -s -L %s' %  opts.repo_list)
    if e:
      print (o)
      exit(1)
    repos = yaml.load_all(o)
  elif exists(opts.repo_list):
    repos = yaml.load(open(opts.repo_list))
  else:
    print ("Error: No such file: %s" % opts.repo_list)
    exit (1)
  repo_cache = {}
  process(repos, opts.dryRun, repo_cache)
