from milestones import *
import re

#Default development branch
# Changes from master branch will be merge in to it
# Any PR open against this will be automatically closed by cms-bot (Pr should be made for master branch)
# For new release cycle just change this and make sure to add its milestone and production branches
CMSSW_DEVEL_BRANCH = "CMSSW_13_0_X"

RELEASE_BRANCH_MILESTONE["master"]=RELEASE_BRANCH_MILESTONE[CMSSW_DEVEL_BRANCH]
RELEASE_BRANCH_PRODUCTION.append("master")
USERS_TO_TRIGGER_HOOKS = set(SPECIAL_RELEASE_MANAGERS + [ m for rel in RELEASE_MANAGERS for m in rel ])

def get_release_managers(branch):
  if branch in RELEASE_MANAGERS: return RELEASE_MANAGERS[branch]
  for exp in RELEASE_MANAGERS:
    if re.match(exp, branch): return RELEASE_MANAGERS[exp]
  return []

def is_closed_branch(branch):
  if branch in RELEASE_BRANCH_CLOSED: return True
  for exp in RELEASE_BRANCH_CLOSED:
    if re.match(exp, branch): return True
  return False

