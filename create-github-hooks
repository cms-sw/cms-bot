#!/usr/bin/env python3
from github import Github
from os.path import expanduser, exists, join, dirname, abspath
from os import environ
from optparse import OptionParser
from github_hooks_config import get_repository_hooks, get_event_hooks
from github_utils import api_rate_limits
import hashlib
from categories import EXTERNAL_REPOS, CMSSW_REPOS, CMSDIST_REPOS
from sys import argv
from socket import setdefaulttimeout
setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(argv[0]))

#Get secret from file
def get_secret(hook_name):
  if "GH_HOOK_SECRET_FILE" in environ: secret_file=environ['GH_HOOK_SECRET_FILE']
  else:
    secret_file = '/data/secrets/' + hook_name
    if not exists(secret_file):
      secret_file = '/data/secrets/github_hook_secret_cmsbot'
  return open(secret_file,'r').read().split('\n')[0].strip()
#match hook config
def match_config(new,old):
  if new["active"] != old.active:
    return False
  elif set(new["events"]) != set(old.events):
    return False
  for key in new["config"]:
    if (not key in old.config) or (key!='secret' and new["config"][key] != old.config[key]):
      return False
  return True
  
#main section
if __name__ == "__main__":
  parser = OptionParser(usage="%prog [-k|--hook <name>] [-r|--repository <repo>] [-f|--force] [-n|--dry-run]")
  parser.add_option("-n", "--dry-run",   dest="dryRun",     action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-f", "--force",     dest="force",     action="store_true", help="Force update github hook", default=False)
  parser.add_option("-r", "--repository",dest="repository", help="Github Repositoy name e.g. cms-sw/cmssw.", type=str, default=None)
  parser.add_option("-e", "--externals", dest="externals", action="store_true", help="Only process CMS externals repositories", default=False)
  parser.add_option("-u", "--users",     dest="users",     action="store_true", help="Only process USER externals repositories", default=False)
  parser.add_option("-c", "--cmssw",     dest="cmssw",     action="store_true", help="Only process "+",".join(CMSSW_REPOS)+" repository", default=False)
  parser.add_option("-d", "--cmsdist",   dest="cmsdist",   action="store_true", help="Only process "+",".join(CMSDIST_REPOS)+" repository", default=False)
  parser.add_option("-a", "--all",       dest="all",       action="store_true", help="Process all CMS repository i.e. externals, cmsdist and cmssw", default=False)
  parser.add_option("-k", "--hook", dest="hook", help="Github Hook name", type=str, default="")
  opts, args = parser.parse_args()

  repos_names = []
  if opts.repository:
    repos_names.append(opts.repository)
  elif opts.all:
    opts.externals = True
    opts.cmssw = True
    opts.cmsdist = True
  elif (not opts.externals) and (not opts.cmssw) and (not opts.cmsdist) and (not opts.users):
    parser.error("Too few arguments, please use either -e, -c , -u or -d")

  if not repos_names:
    if opts.externals: repos_names = repos_names + EXTERNAL_REPOS
    if opts.cmssw: repos_names = repos_names + CMSSW_REPOS
    if opts.cmsdist: repos_names = repos_names + CMSDIST_REPOS
    if opts.users:
      from glob import glob
      for rconf in glob(join(SCRIPT_DIR,"repos","*","*","repo_config.py")):
        repos_names.append("/".join(rconf.split("/")[-3:-1]))
        print("Added User repo: ",repos_names[-1])

  ghx = Github(login_or_token = open(expanduser("~/.github-token")).read().strip())
  api_rate_limits(ghx)
  #get repos to be processed
  repos = {}
  for r in set(repos_names):
    if not "/" in r:
      for repo in ghx.get_user(r).get_repos():
        repos[repo.full_name]=repo
      api_rate_limits(ghx)
    else:
      repos[r]=None

  #process repos
  for repo_name in repos:
    gh = ghx
    isUserRepo = False
    if exists (join(SCRIPT_DIR,"repos",repo_name,"repo_config.py")):
      exec('from repos.'+repo_name.replace("/",".")+' import repo_config')
      if not repo_config.ADD_WEB_HOOK:
        print("Skipped Web hook:",repo_name)
        continue
      isUserRepo = True
      gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
      repo_name = repo_config.GH_REPO_FULLNAME
    xfile = repo_name.replace("/","-")+".done"
    if exists(xfile): continue
    print("Checking for repo ",repo_name)
    if isUserRepo:
      hk_conf = get_event_hooks(repo_config.VALID_WEB_HOOKS)
    else:
      hk_conf = get_repository_hooks (repo_name, opts.hook)
    hooks = list(hk_conf.keys())
    if not hooks:
      print("==>Warning: No hook found for repository",repo_name)
      continue

    print("Found hooks:",hooks)
    repo = repos[repo_name]
    if not repo: repo = gh.get_repo(repo_name)
    repo_hooks_all = {}
    for hook in repo.get_hooks():
      if "name" in hook.config:
        repo_hooks_all[ hook.config['name'] ] = hook 
    api_rate_limits(gh)
    print("Dryrun:",opts.dryRun)
    for hook in hooks:
      print("checking for web hook", hook)
      hook_conf = hk_conf[hook]
      hook_conf["name"] = "web"
      hook_conf["config"]["insecure_ssl"] = "1"
      hook_conf["config"]["secret"] = get_secret(hook)
      hook_conf["config"]["name"] = hook
      hook_conf["config"]["data"] = hashlib.sha256(hook_conf["config"]["secret"].encode()).hexdigest()
      if hook in repo_hooks_all:
        old_hook = repo_hooks_all[hook]
        if opts.force or not match_config(hook_conf,old_hook):
          if not opts.dryRun:
            old_hook.edit(**hook_conf)
            api_rate_limits(gh)
          print("hook updated",hook)
        else:
          print("Hook configuration is same",hook)
      else:
        if not opts.dryRun:
          repo.create_hook(**hook_conf)
          api_rate_limits(gh)
        print("Hook created in github.....success",hook)
    ref = open(xfile,"w")
    ref.close()
