from urllib2 import urlopen
from json import loads
from commands import getstatusoutput
from os.path import exists, dirname, abspath
import re
from cms_static import GH_CMSSW_ORGANIZATION

try:
  scriptPath = dirname(abspath(__file__))
except Exception, e :
  scriptPath = dirname(abspath(argv[0]))

def format(s, **kwds): return s % kwds

def get_ported_PRs(repo, src_branch, des_branch):
  done_prs_id = {}
  prRe = re.compile('Automatically ported from '+src_branch+' #(\d+)\s+.*',re.MULTILINE)
  for pr in repo.get_pulls(base=des_branch):
    body = pr.body.encode("ascii", "ignore")
    m  = prRe.search(body)
    if m:
      done_prs_id[int(m.group(1))]=pr.number
      print m.group(1),"=>",pr.number
  return done_prs_id

def port_pr(repo, pr_num, des_branch, dryRun=False):
  pr = repo.get_pull(pr_num)
  if pr.base.ref == des_branch:
    print "Warning: Requested to make a PR to same branch",pr.base.ref
    return False
  done_prs_id = get_ported_PRs(repo, pr.base.ref, des_branch)
  if done_prs_id.has_key(pr_num):
    print "Already ported as #",done_prs_id[pr.number]
    return True
  branch = repo.get_branch(des_branch)
  print "Preparing checkout area:",pr_num,repo.full_name,pr.head.user.login,pr.head.ref,des_branch
  prepare_cmd = format("%(cmsbot)s/prepare-repo-clone-for-port.sh %(pr)s %(pr_user)s/%(pr_branch)s %(repo)s %(des_branch)s",
                       cmsbot=scriptPath,
                       pr=pr_num,
                       repo=repo.full_name,
                       pr_user=pr.head.user.login,
                       pr_branch=pr.head.ref,
                       des_branch=des_branch)
  err, out = getstatusoutput(prepare_cmd)
  print out
  if err: return False
  all_commits = set([])
  for c in pr.get_commits():
    all_commits.add(c.sha)
    git_cmd = format("cd %(clone_dir)s; git cherry-pick -x %(commit)s",
                         clone_dir=pr.base.repo.name,
                         commit=c.sha)
    err, out = getstatusoutput(git_cmd)
    print out
    if err: return False
  git_cmd = format("cd %(clone_dir)s; git log %(des_branch)s..",
                   clone_dir=pr.base.repo.name,
                   des_branch=des_branch)
  err , out = getstatusoutput(git_cmd)
  print out
  if err: return False
  last_commit = None
  new_commit = None
  new_commits = {}
  for line in out.split("\n"):
    m = re.match('^commit\s+([0-9a-f]+)$',line)
    if m:
      print "New commit:",m.group(1),last_commit
      if last_commit:
        new_commits[new_commit]=last_commit
      new_commit = m.group(1)
      new_commits[new_commit]=None
      continue
    m =re.match('^\s*\(cherry\s+picked\s+from\s+commit\s([0-9a-f]+)\)$',line)
    if m:
      print "found commit",m.group(1)
      last_commit=m.group(1)
  if last_commit: new_commits[new_commit]=last_commit
  if pr.commits!=len(new_commits):
    print "Error: PR has ",pr.commits," commits while we only found ",len(new_commits),":",new_commits
  for c in new_commits:
    all_commits.remove(new_commits[c])
  if all_commits:
    print "Something went wrong: Following commists not cherry-picked",all_commits
    return False
  git_cmd = format("cd %(clone_dir)s; git rev-parse --abbrev-ref HEAD", clone_dir=pr.base.repo.name)
  err , out = getstatusoutput(git_cmd)
  print out
  if err or not out.startswith("port-"+str(pr_num)+"-"): return False
  new_branch = out
  git_cmd = format("cd %(clone_dir)s; git push origin %(new_branch)s",
                   clone_dir=pr.base.repo.name,
                   new_branch=new_branch)
  if not dryRun:
    err , out = getstatusoutput(git_cmd)
    print out
    if err: return False
  else:
    print "DryRun: should have push %s branch" % new_branch
  newHead = "%s:%s" % (GH_CMSSW_ORGANIZATION, new_branch)
  newBody = pr.body + "\nAutomatically ported from " + pr.base.ref + " #%s (original by @%s)." % (pr_num, str(pr.head.user.login))
  print newHead
  print newBody
  if not dryRun:
    newPR = repo.create_pull(title=pr.title, body=newBody, base=des_branch, head=newHead)
  else:
    print "DryRun: should have created Pull Request for %s using %s" % (des_branch, newHead)
  print "Every thing looks good"
  git_cmd = format("cd %(clone_dir)s; git branch -d %(new_branch)s",
                   clone_dir=pr.base.repo.name,
                   new_branch=new_branch)
  err, out = getstatusoutput(git_cmd)
  print "Local branch %s deleted" % new_branch
  return True
    

