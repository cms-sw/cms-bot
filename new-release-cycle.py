#!/usr/bin/env python
from __future__ import print_function
from github import Github, GithubException
from os.path import expanduser, dirname, abspath, join
from optparse import OptionParser
from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, GH_CMSDIST_REPO
from sys import exit, argv
from _py2with3compatibility import run_cmd
from socket import setdefaulttimeout
from releases import CMSSW_DEVEL_BRANCH
setdefaulttimeout(120)

# python2 compatibility
try:
    input = raw_input
except NameError:
    pass

try:
  scriptPath = dirname(abspath(__file__))
except Exception as e :
  scriptPath = dirname(abspath(argv[0]))

###############################################################
def create_branch(repo, base_branch, new_branch, dryRun=False):
  while True:
    print("Creating new branch '%s' based on '%s'" % (new_branch, base_branch))
    res = input("OK to create this branch [Y/N/Q]: ")
    if res=="Y": break
    if res=="N": return
    if res=="Q": exit(1)
  base_ref = repo.get_branch(base_branch)
  print("Base branch %s has sha %s" % (base_branch, base_ref.commit.sha))
  try:
    repo.get_branch(new_branch)
    print("Branch already exists: ",new_branch)
    return
  except GithubException as e:
    if not "Branch not found" in e.data['message']: raise e
  if not dryRun:
    repo.create_git_ref ("refs/heads/"+new_branch, base_ref.commit.sha)
    print("Created new branch ",new_branch," based on ",base_ref.commit.sha)
  else:
    print("DryRun: Creating new branch ",new_branch," based on ",base_ref.commit.sha)
  return

def get_milestone(repo, milestone_name):
  milestones = repo.get_milestones()
  for item in repo.get_milestones():
    if milestone_name in item.title: return item
  return None

def create_milestone(repo, milestone_name, dryRun=False):
  print("Creating new milestone '%s'" % milestone_name)
  milestone = get_milestone (repo, milestone_name)
  if milestone: return milestone
  if not dryRun:
    milestone = repo.create_milestone (milestone_name)
    print("Created milestone %s with number %s" % (milestone_name, str(milestone.number)))
  else:
    print("DryRun: Creating new milestone %s" % milestone_name)
  return milestone

def update_milestone(repo, source, srcMilestone, desMilestone, dryRun=False):
  pulls = repo.get_pulls(base=source, state="open", sort="created", direction="asc")
  for pr in pulls:
    print("Wroking on PR ",pr.number,"with milestone",pr.milestone.number)
    if (pr.milestone.number == desMilestone.number):
      print("  Milestone already updated for PR:",pr.number)
    elif pr.milestone.number == srcMilestone.number:
      if not dryRun:
        issue = repo.get_issue(pr.number)
        issue.edit(milestone=desMilestone)
      print("  Updated milestone for PR:",pr.number)
    else:
      print("  Invalid Source Milestone:",pr.milestone.number)
  return

def add_milestone_in_cmsbot(new_br, cmssw_brs, milestone, dryRun=False):
  print("Updating milestones.py")
  from releases import RELEASE_BRANCH_MILESTONE
  if new_br in RELEASE_BRANCH_MILESTONE:
    print("Warning: Not updating milestones.py as it already have changes for new release cycle %s" % new_br)
    return
  with open(join(scriptPath,"milestones.py"), "a") as relFile:
    relFile.write('\n######################################################################\n')
    relFile.write('# Automatically added by cms-bot for %s release cycle\n' % (new_br))
    relFile.write('######################################################################\n')
    relFile.write('RELEASE_BRANCH_MILESTONE["%s"]=%s\n' % (new_br, 0 if dryRun else milestone.number))
    relFile.write('RELEASE_BRANCH_PRODUCTION.append("%s")\n' % (new_br))
    for br in cmssw_brs:
      if new_br!=br: relFile.write('RELEASE_BRANCH_PRODUCTION.append("%s")\n' % (br))
  return

def update_dev_branch(new_br, dryRun=False):
  print("Updating releases.py")
  err, out = run_cmd("sed -i -e 's|^ *CMSSW_DEVEL_BRANCH *=.*$|CMSSW_DEVEL_BRANCH = \"%s\"|' %s" % (new_br,join(scriptPath,"releases.py")))
  return

def config_map_branches(new_br, dev_br, config_file):
  cmssw_brs = {}
  cmsdist_brs = {}
  new_cyc = new_br[:-1]
  dev_cyc = dev_br[:-1]
  new_ibs    = []
  new_config = []
  for l in [ l.strip() for l in open(config_file).readlines()]:
    if "RELEASE_QUEUE="+new_cyc in l: continue
    l = l.replace("RELEASE_BRANCH=master;","RELEASE_BRANCH=%s;" % dev_br)
    new_config.append(l)
    if ("RELEASE_BRANCH="+dev_cyc in l) and (not 'DISABLED=' in l):
      cmssw_br = l.split("RELEASE_BRANCH=")[1].split(";")[0]
      cmssw_brs[cmssw_br]=cmssw_br.replace(dev_cyc, new_cyc)
      cmsdist_br = l.split("CMSDIST_TAG=")[1].split(";")[0]
      cmsdist_brs[cmsdist_br]=cmsdist_br.replace(dev_br, new_br)
      new_ibs.append(l.replace(dev_cyc, new_cyc).replace("RELEASE_BRANCH="+new_br+";","RELEASE_BRANCH=master;"))
  return (cmssw_brs, cmsdist_brs, new_ibs+new_config)

def update_config_map(new_br, dryRun=False):
  print("Updating config.map")
  config_file = join(scriptPath,"config.map")
  e , o = run_cmd("grep 'RELEASE_QUEUE=%s;' %s | grep 'PROD_ARCH=1'" % (new_br, config_file))
  if new_br in o:
    print("Warning: Not updating config.map as it already have changes for new release cycle %s" % new_br)
    cmssw_brs, cmsdist_brs, new_config = config_map_branches(new_br, CMSSW_DEVEL_BRANCH, config_file)
    return (cmssw_brs, cmsdist_brs)
  e, dev_br = run_cmd("grep 'RELEASE_BRANCH=master;' %s | grep 'PROD_ARCH=1' | sed 's|.*RELEASE_QUEUE=||;s|;.*||' | sort -u" % config_file)
  if e:
    print("ERROR: unable to find current dev release")
    exit(1)
  if len(dev_br.split("\n"))!=1:
    print("ERROR: None or more than one dev release cycles found. %s" % dev_br)
    exit(1)
  if dev_br != CMSSW_DEVEL_BRANCH:
    print("ERROR: current dev branch  '%s' found in config.map does not match the one set in release.py '%s'" % (dev_br, CMSSW_DEVEL_BRANCH))
    exit(1)  
  cmssw_brs, cmsdist_brs, new_config = config_map_branches(new_br, dev_br, config_file)
  new_config_ref = open(config_file,"w")
  for l in new_config: new_config_ref.write(l+"\n")
  new_config_ref.close()
  return (cmssw_brs, cmsdist_brs)

def update_forward_port(new_br, dryRun=False):
  print("Updating forward_ports_map.py")
  from forward_ports_map import GIT_REPO_FWPORTS
  if new_br in GIT_REPO_FWPORTS["cmssw"]: 
    print("Warning: Not updating forward_ports_map.py as it already have changes for new release cycle %s" % new_br)
    return
  fwdport_file = join(scriptPath,"forward_ports_map.py")
  new_fwd = []
  e, o = run_cmd("grep GIT_REPO_FWPORTS %s | grep '%s'" % (fwdport_file, CMSSW_DEVEL_BRANCH))
  if e:
    print("ERROR: Unable to find forward ports for existsing development release %s" % CMSSW_DEVEL_BRANCH)
    exit (1)
  new_cyc = new_br[:-1]
  dev_cyc = CMSSW_DEVEL_BRANCH[:-1]
  with open(fwdport_file, "a") as ref:
    ref.write('\n#Automatically added\n')
    for l in o.split("\n"):
      ref.write('%s\n' % l.replace(dev_cyc, new_cyc))
  return

def update_release_map(new_br, dryRun=False):
  print("Updating releases.map")
  relmap_file = join(scriptPath,"releases.map")
  e, o = run_cmd("grep 'type=Development;state=IB;prodarch=1;' %s | grep 'label=%s;'" % (relmap_file, new_br))
  if new_br in o:
    print("Warning: Not updating releases.map as it already have changes for new release cycle %s" % new_br)
    return
  e, map_line = run_cmd("grep 'type=Development;state=IB;prodarch=1;' %s | grep 'label=%s;'" % (relmap_file, CMSSW_DEVEL_BRANCH))
  if e:
    print("ERROR: Unable to find current development release '%s' in releases.map" % CMSSW_DEVEL_BRANCH)
    exit(1)
  if len(map_line.split("\n"))>1:
    print("ERROR: Found multiple entrie for '%s' in releases.map" % CMSSW_DEVEL_BRANCH)
    print(map_line)
    exit(1)
  run_cmd("echo '%s' > %s.new" % (map_line.replace('label=%s;' % CMSSW_DEVEL_BRANCH, 'label=%s;' % new_br),relmap_file))
  run_cmd("cat %s >> %s.new" % (relmap_file,relmap_file))
  run_cmd("mv %s.new %s" % (relmap_file,relmap_file))
  
def process(cycle, dryRun):
  gh = Github(login_or_token=open(expanduser("~/.github-token")).read().strip())
  cmssw_repo   = gh.get_repo(GH_CMSSW_ORGANIZATION+"/"+GH_CMSSW_REPO)
  srcMileStone = get_milestone(cmssw_repo, CMSSW_DEVEL_BRANCH)

  if not srcMileStone:
    print("ERROR: Unable to get milestone for %s" % CMSSW_DEVEL_BRANCH)
    exit(1)

  #make sure that existing dev IB use the dev branch instead of master branch
  cmssw_brs, cmsdist_brs = update_config_map(cycle, dryRun)

  #update forward port map
  update_forward_port(cycle, dryRun)

  #update forward port map
  update_release_map(cycle, dryRun)

  #Create milestone
  desMileStone = create_milestone(cmssw_repo, cycle, dryRun)

  #Add milestone on
  add_milestone_in_cmsbot (cycle, list(cmssw_brs.values()), desMileStone, dryRun)

  #Add devel branch
  update_dev_branch(cycle, dryRun)

  #Create cmssw branches
  create_branch (cmssw_repo, "master", cycle, dryRun)

  #Update milestone for existing Open PRs
  if dryRun: desMileStone = srcMileStone
  update_milestone(cmssw_repo, "master", srcMileStone, desMileStone, dryRun)

  #create cmssw branches
  for dev_br in list(cmssw_brs.keys()):
    new_br = cmssw_brs[dev_br]
    if new_br==cycle: continue
    create_branch (cmssw_repo, dev_br, new_br, dryRun)

  #create cmsdist branches
  cmsdist_repo = gh.get_repo(GH_CMSSW_ORGANIZATION+"/"+GH_CMSDIST_REPO)
  for dev_br in list(cmsdist_brs.keys()):
    new_br = cmsdist_brs[dev_br]
    create_branch (cmsdist_repo, dev_br, new_br, dryRun)

  err, out = run_cmd("cd %s; git diff origin" % scriptPath)
  print("GIT DIFF:\n",out)
  print("\nIf the changes above looks good then please commit and push these to github")
  return True

###############################################################
if __name__ == "__main__":
  parser = OptionParser(usage="%prog <pull-request-id>")
  parser.add_option("-n", "--dry-run",   dest="dryRun", action="store_true", help="Do not modify Github", default=False)
  parser.add_option("-c", "--cycle",     dest="cycle",  help="Release cycle name e.g CMSSW_10_1_X", type=str, default='None')
  parser.add_option("-o", "--old-cycle", dest="old_cycle",  help="Existing development release cycle e.g CMSSW_10_0_X. Default is "+CMSSW_DEVEL_BRANCH+" obtained from releases.py", type=str, default=CMSSW_DEVEL_BRANCH)
  opts, args = parser.parse_args()

  if len(args) > 0: parser.error("Too many arguments")
  if not opts.cycle or not opts.cycle.endswith("_X"): parser.error("Invalid cycle '"+str(opts.cycle)+"' it must end with _X")
  if opts.old_cycle != CMSSW_DEVEL_BRANCH: CMSSW_DEVEL_BRANCH=opts.old_cycle
  process (opts.cycle, opts.dryRun)
