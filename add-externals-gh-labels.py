#!/usr/bin/env python
from github import Github
from os.path import expanduser
from githublabels import LABEL_TYPES, COMMON_LABELS, COMPARISON_LABELS, CMSSW_BUILD_LABELS
from categories import COMMON_CATEGORIES, EXTERNAL_CATEGORIES, EXTERNAL_REPOS, CMSSW_REPOS, CMSDIST_REPOS, CMSSW_CATEGORIES
from datetime import datetime
from socket import setdefaulttimeout
setdefaulttimeout(120)

def setRepoLabels (gh, repo_name, all_labels, dryRun=False):
  repos = []
  if not "/" in repo_name:
    user = gh.get_user(repo_name)
    for repo in user.get_repos():
      repos.append(repo)
  else:
    repos.append(gh.get_repo(repo_name))

  print 'API Rate Limit'
  print 'Limit, Remaining: ', gh.rate_limiting
  print 'Reset time (GMT): ', datetime.fromtimestamp(gh.rate_limiting_resettime)
  for repo in repos:
    print "Checking repository ", repo.full_name
    cur_labels = {}
    for lab in repo.get_labels():
      cur_labels [lab.name]=lab
    for lab in all_labels:
      if not lab in cur_labels:
        print "  Creating new label ",lab,"=>",all_labels[lab]
        if not dryRun: repo.create_label(lab, all_labels[lab])
      elif cur_labels[lab].color != all_labels[lab]:
        if not dryRun: cur_labels[lab].edit(lab, all_labels[lab])
        print "  Label ",lab," color updatd: ",cur_labels[lab].color ," => ",all_labels[lab]

  print 'API Rate Limit'
  print 'Limit, Remaining: ', gh.rate_limiting
  print 'Reset time (GMT): ', datetime.fromtimestamp(gh.rate_limiting_resettime)

if __name__ == "__main__":
  from optparse import OptionParser
  parser = OptionParser(usage="%prog [-n|--dry-run] [-e|--externals] [-c|--cmssw]  [-d|--cmsdist] [-a|--all]")
  parser.add_option("-n", "--dry-run",   dest="dryRun",    action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-e", "--externals", dest="externals", action="store_true", help="Only process CMS externals repositories", default=False)
  parser.add_option("-c", "--cmssw",     dest="cmssw",     action="store_true", help="Only process "+",".join(CMSSW_REPOS)+" repository", default=False)
  parser.add_option("-d", "--cmsdist",   dest="cmsdist",   action="store_true", help="Only process "+",".join(CMSDIST_REPOS)+" repository", default=False)
  parser.add_option("-a", "--all",       dest="all",       action="store_true", help="Process all CMS repository i.e. externals, cmsdist and cmssw", default=False)
  opts, args = parser.parse_args()

  if opts.all:
    opts.externals = True
    opts.cmssw = True
    opts.cmsdist = True
  elif (not opts.externals) and (not opts.cmssw) and (not opts.cmsdist):
    parser.error("Too few arguments, please use either -e, -c or -d")

  gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
  if opts.externals:
    all_labels = COMMON_LABELS
    for cat in COMMON_CATEGORIES+EXTERNAL_CATEGORIES:
      for lab in LABEL_TYPES:
        all_labels[cat+"-"+lab]=LABEL_TYPES[lab]
    for repo_name in EXTERNAL_REPOS:
      setRepoLabels (gh, repo_name, all_labels, opts.dryRun)

  if opts.cmssw:
    all_labels = COMMON_LABELS
    for lab in COMPARISON_LABELS:
      all_labels[lab] = COMPARISON_LABELS[lab]
    for lab in CMSSW_BUILD_LABELS:
      all_labels[lab] = CMSSW_BUILD_LABELS[lab]
    for cat in COMMON_CATEGORIES+CMSSW_CATEGORIES.keys():
      for lab in LABEL_TYPES:
        all_labels[cat+"-"+lab]=LABEL_TYPES[lab]
    for repo_name in CMSSW_REPOS:
      setRepoLabels (gh, repo_name, all_labels, opts.dryRun)

  if opts.cmsdist:
    all_labels = COMMON_LABELS
    for cat in COMMON_CATEGORIES+CMSSW_CATEGORIES.keys():
      for lab in LABEL_TYPES:
        all_labels[cat+"-"+lab]=LABEL_TYPES[lab]
    for repo_name in CMSDIST_REPOS:
      setRepoLabels (gh, repo_name, all_labels, opts.dryRun)

