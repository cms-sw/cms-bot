from urllib2 import urlopen
import json
from commands import getstatusoutput
from os.path import exists, dirname, abspath
import re
from cms_static import GH_CMSSW_ORGANIZATION
from github import UnknownObjectException

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

def prs2relnotes (notes, ref_repo=""):
  new_notes = {}
  for pr_num in notes:
    new_notes[pr_num]=format("- %(ref_repo)s#%(pull_request)s from @%(author)s: %(title)s",
                                  ref_repo=ref_repo,
                                  pull_request=pr_num,
                                  author=notes[pr_num]['author'],
                                  title=notes[pr_num]['title'])
  return new_notes

def cache_invalid_pr (pr_id, cache):
  if not 'invalid_prs' in cache: cache['invalid_prs']=[]
  cache['invalid_prs'].append(pr_id)
  cache['dirty']=True

def fill_notes_description(notes, repo, cache={}):
  new_notes = {}
  for log_line in notes.splitlines():
    items = log_line.split(" ")
    author = items[1]
    pr_number= items[0]
    if cache and (pr_number in cache):
      new_notes[pr_number]=cache[pr_number]
      print 'Read from cache ',pr_number
      continue
    parent_hash = items.pop()
    pr_hash_id = pr_number+":"+parent_hash
    if 'invalid_prs' in cache and pr_hash_id in cache['invalid_prs']: continue
    print "Checking ",pr_number,author,parent_hash
    try:
      pr = repo.get_pull(int(pr_number))
      ok = True
      if pr.head.user.login!=author:
        print "  Author mismatch:",pr.head.user.login
        ok=False
      if pr.head.sha!=parent_hash:
        print "  sha mismatch:",pr.head.sha
        ok=False
      if not ok:
        print "  Invalid/Indirect PR"
        cache_invalid_pr (pr_hash_id,cache)
        continue
      new_notes[pr_number]={
        'author' : author,
        'title' : pr.title.encode("ascii", "ignore"),
        'user_ref' : pr.head.ref.encode("ascii", "ignore"),
        'hash' : parent_hash,
        'branch' : pr.base.ref.encode("ascii", "ignore") }
      if not pr_number in cache:
        cache[pr_number]=new_notes[pr_number]
        cache['dirty']=True
    except UnknownObjectException as e:
      print "ERR:",e
      cache_invalid_pr (pr_hash_id,cache)
      continue
  return new_notes

def get_merge_prs(prev_tag, this_tag, git_dir, repo, cache={}):
  print "Getting merged Pull Requests b/w",prev_tag, this_tag
  error, notes = getstatusoutput(format("GIT_DIR=%(git_dir)s"
                                      " git log --graph --merges --pretty='%%s: %%P' %(previous)s..%(release)s | "
                                      " grep ' Merge pull request #[1-9][0-9]* from ' | "
                                      " sed 's|^.* Merge pull request #||' | "
                                      " sed 's|/[^:]*:||;s|from ||'",
                                      git_dir=git_dir,
                                      previous=prev_tag,
                                      release=this_tag))
  if error:
    print "Error while getting release notes."
    print notes
    exit(1)
  return fill_notes_description(notes, repo, cache)

def save_prs_cache(cache, cache_file):
  if cache['dirty']:
    del cache['dirty']
    with open(cache_file, "w") as out_json:
      json.dump(cache,out_json,indent=2, sort_keys=True)
      out_json.close()
    cache['dirty']=False

def read_prs_cache(cache_file):
  cache = {}
  if exists(cache_file):
    with open(cache_file) as json_file:
      cache = json.loads(json_file.read())
      json_file.close()
  cache['dirty']=False
  return cache

