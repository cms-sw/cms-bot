#!/usr/bin/env python
import sys, time, threading
from commands import getstatusoutput
from os.path import exists, join, abspath, dirname
from sys import exit, argv
import re
from optparse import OptionParser
try:
  SCRIPT_DIR = dirname(abspath(__file__))
except Exception, e :
  SCRIPT_DIR = dirname(abspath(argv[0]))

def process_commit(commit,id):
  err, out = getstatusoutput("%s/process-commit.sh %s" % (SCRIPT_DIR, commit))
  if err:
    print "[%s]:%s: %s\n%s" % (str(id), str(err), commit, out) 

parser = OptionParser(usage="%prog -b|--branch <cmssw-branch>")
parser.add_option("-b", "--branch", dest="branch", help="Default cmssw branch", default="CMSSW_8_1_X")
parser.add_option("-j", "--jobs",   dest="jobs",   help="Number of parallel jobs to run", type=int, default=1)
opts, args = parser.parse_args()

max_thd = opts.jobs
if max_thd<1: max_thd=1

repo = "stitched"
if not exists(repo):
  print "Cloning ",repo
  err, out = getstatusoutput("git clone git@github.com:cms-sw/%s" % repo)
  if err:
    print out
    exit(1)

print "Getting %s updates" % repo
err, out = getstatusoutput("cd %s && git clean -fdx && git checkout %s && git pull" % (repo, "master"))
if err:
  print out
  exit(1)

err, last_commit = getstatusoutput("cat stitched/.cmssw-commit")
last_commit = last_commit.strip(' \t\n\r')
if err or not re.match("^[0-9a-f]{40}$",last_commit):
  print "Unable to find last commit of cmssw\n%s" % last_commit
  exit(1)
print "Getting new commits since",last_commit

err, out = getstatusoutput("ls -d %s/*/* | sed 's|^%s/||'" % ("stitched","stitched"))
if err:
  print out
  exit(1)

DIRS = [x for x in out.split("\n")]
err, out = getstatusoutput("mkdir -p commits")
pfile = open('commits/packages', 'w')
for d in DIRS:
  pfile.write('^'+d+"/\n")
pfile.close()

err, out = getstatusoutput("cd %s && git remote | grep '^cmssw$' | wc -l" % repo)
if err:
  print out
  exit(1)

if out == "0":
  err, out = getstatusoutput("cd %s && git remote add cmssw git@github.com:cms-sw/cmssw" % repo)
  if err:
    print out
    exit(1)

print "Fetching cmssw branch ",opts.branch
err, out = getstatusoutput("cd %s && git fetch cmssw %s:%s && git checkout %s" % (repo, opts.branch, opts.branch, opts.branch))
if err:
  print out
  exit(1)

new_commits = []
err, out = getstatusoutput('cd %s && git log --reverse --pretty=format:"%%H" %s..%s > ../commits/commits.txt' % (repo, last_commit, opts.branch))
if err:
  print out
  exit(1)

getstatusoutput('echo >> commits/commits.txt')
err, out = getstatusoutput('cat commits/commits.txt')
for c in out.split("\n"):
  if not re.match("^[0-9a-f]{40}$",c):
    print out
    exit (1)
  new_commits.append(c)

threads = []
ii=0
it=str(len(new_commits))
for c in new_commits:
  ii=ii+1
  print "%s/%s %s" % (str(ii), it, c)
  if max_thd<=1:
    process_commit(c, ii)
    continue
  while True:
    threads = [t for t in threads if t.is_alive()]
    if len(threads) < max_thd: break
    time.sleep(.1)
  try:
    t = threading.Thread(target=process_commit, args=(c,ii,))
    t.start()
    threads.append(t)
  except Exception, e:
    print str(e)
    exit(1)

for t in threads: t.join()
print "DONE"
