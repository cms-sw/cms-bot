#!/usr/bin/env python3
from github import Github
from os.path import expanduser, dirname, abspath, join, exists
from githublabels import LABEL_TYPES, COMMON_LABELS, COMPARISON_LABELS, CMSSW_BUILD_LABELS, LABEL_COLORS
from categories import COMMON_CATEGORIES, EXTERNAL_CATEGORIES, EXTERNAL_REPOS, CMSSW_REPOS, CMSSW_CATEGORIES
from cms_static import VALID_CMS_SW_REPOS_FOR_TESTS, GH_CMSSW_ORGANIZATION
from socket import setdefaulttimeout
from github_utils import api_rate_limits
from cmsutils import get_config_map_properties
from sys import argv
setdefaulttimeout(120)
SCRIPT_DIR = dirname(abspath(argv[0]))

def setRepoLabels (gh, repo_name, all_labels, dryRun=False, ignore=[]):
  repos = []
  if not "/" in repo_name:
    user = gh.get_user(repo_name)
    for repo in user.get_repos():
      skip = False
      if repo.full_name in ignore:
        skip = True
      elif repo_name==GH_CMSSW_ORGANIZATION:
        if repo.name not in VALID_CMS_SW_REPOS_FOR_TESTS:
          skip = True
      if skip:
        print("Ignoring repo:",repo.full_name)
        continue
      repos.append(repo)
  else:
    repos.append(gh.get_repo(repo_name))
  api_rate_limits(gh)
  for repo in repos:
    print("Checking repository ", repo.full_name, ", DryRun:",dryRun)
    xfile = repo.full_name.replace("/","-")+".done"
    if exists(xfile): continue
    cur_labels = {}
    for lab in repo.get_labels():
      cur_labels [lab.name]=lab
    api_rate_limits(gh)
    for lab in all_labels:
      if not lab in cur_labels:
        print("  Creating new label ",lab,"=>",all_labels[lab])
        if not dryRun:
          repo.create_label(lab, all_labels[lab])
          api_rate_limits(gh)
      elif cur_labels[lab].color != all_labels[lab]:
        if not dryRun:
          cur_labels[lab].edit(lab, all_labels[lab])
          api_rate_limits(gh)
        print("  Label ",lab," color updated: ",cur_labels[lab].color ," => ",all_labels[lab])
    ref = open(xfile,"w")
    ref.close()

if __name__ == "__main__":
  from optparse import OptionParser
  parser = OptionParser(usage="%prog [-n|--dry-run] [-e|--externals] [-c|--cmssw]  [-a|--all]")
  parser.add_option("-n", "--dry-run",   dest="dryRun",    action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-e", "--externals", dest="externals", action="store_true", help="Only process CMS externals repositories", default=False)
  parser.add_option("-u", "--users",     dest="users",     action="store_true", help="Only process Users externals repositories", default=False)
  parser.add_option("-c", "--cmssw",     dest="cmssw",     action="store_true", help="Only process "+",".join(CMSSW_REPOS)+" repository", default=False)
  parser.add_option("-r", "--repository",dest="repository",                     help="Only process the selected repository.", type=str, default=None)
  parser.add_option("-a", "--all",       dest="all",       action="store_true", help="Process all CMS repository i.e. externals and cmssw", default=False)
  opts, args = parser.parse_args()

  if opts.all:
    opts.externals = True
    opts.cmssw = True
  elif (not opts.externals) and (not opts.cmssw) and (not opts.users):
    parser.error("Too few arguments, please use either -e, -c or -u")

  import repo_config
  gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
  api_rate_limits(gh)

  if opts.cmssw or opts.externals:
    all_labels = COMMON_LABELS
    for cat in COMMON_CATEGORIES+EXTERNAL_CATEGORIES+list(CMSSW_CATEGORIES.keys()):
      for lab in LABEL_TYPES:
        all_labels[cat+"-"+lab]=LABEL_TYPES[lab]
    for lab in COMPARISON_LABELS:
      all_labels[lab] = COMPARISON_LABELS[lab]

  if opts.externals:
    repos = EXTERNAL_REPOS if not opts.repository else [opts.repository]
    for repo_name in repos:
      setRepoLabels (gh, repo_name, all_labels, opts.dryRun, ignore=CMSSW_REPOS)

  if opts.cmssw:
    for lab in CMSSW_BUILD_LABELS:
      all_labels[lab] = CMSSW_BUILD_LABELS[lab]
    specs = get_config_map_properties()
    for s in specs:
      if 'DISABLED' in s: continue
      if 'IB_ONLY' in s: continue
      arch = s['SCRAM_ARCH']
      for ltype in ['build', 'installation', 'tool-conf', 'upload']:
        all_labels['%s-%s-error' % (arch, ltype)] = LABEL_COLORS["rejected"]
        all_labels['%s-%s-ok' % (arch, ltype)] =    LABEL_COLORS["approved"]
      for inproc in [ 'building', 'tool-conf-building', 'uploading', 'build-queued', 'tool-conf-waiting']:
        all_labels[arch+'-'+inproc] = LABEL_COLORS["hold"]
      all_labels[arch+'-finished'] = LABEL_COLORS["approved"]
    repos = CMSSW_REPOS if not opts.repository else [opts.repository]
    for repo_name in CMSSW_REPOS:
      setRepoLabels (gh, repo_name, all_labels, opts.dryRun)

  if opts.users:
    from glob import glob
    for rconf in glob(join(SCRIPT_DIR,"repos","*","*","repo_config.py")):
      repo_data = rconf.split("/")[-4:-1]
      exec('from '+".".join(repo_data)+' import repo_config')
      try:
        if not repo_config.ADD_LABELS: continue
      except: continue
      exec('from '+".".join(repo_data)+' import categories')
      print(repo_config.GH_TOKEN, repo_config.GH_REPO_FULLNAME)
      gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())
      all_labels = COMMON_LABELS
      for lab in COMPARISON_LABELS:
        all_labels[lab] = COMPARISON_LABELS[lab]
      for cat in categories.COMMON_CATEGORIES+list(categories.CMSSW_CATEGORIES.keys()):
        for lab in LABEL_TYPES:
          all_labels[cat+"-"+lab]=LABEL_TYPES[lab]
      setRepoLabels (gh, repo_config.GH_REPO_FULLNAME, all_labels, opts.dryRun)

