#cmsdist/comp rules
from re import match,IGNORECASE

#Merge format: "user" : [ regexp for valid commands, regexp of allowed branches, regexp of not allowed branches ]
CMSSW_BRANCHES   = "^IB/CMSSW_.+$"
ALL_BRANCHES     = ".+"
WMAGENT_BRANCHES = "^comp_gcc493$"
CMSDIST_PERMISSIONS = {
  "BrunoCoimbra"   : [ ".+", ALL_BRANCHES , CMSSW_BRANCHES ],
  "h4d4"           : [ ".+", ALL_BRANCHES , CMSSW_BRANCHES ],
  "amaltaro"       : [ ".+", WMAGENT_BRANCHES , CMSSW_BRANCHES ],
  "ticoann"        : [ ".+", WMAGENT_BRANCHES , CMSSW_BRANCHES ],
}

VALID_COMMENTS = {
  "^(please(\s*,|)\s+|)merge$"    : "merge",
  "^(please(\s*,|)\s+|)close$"    : "close",
  "^(please(\s*,|)\s+|)(re|)open$": "open",
  "^ping$"                        : "ping",
}

def getCommentCommand(comment):
  comment = comment.strip().lower()
  for regex in VALID_COMMENTS:
    if match(regex,comment,IGNORECASE): return VALID_COMMENTS[regex]
  return None

def hasRights(user, branch, type):
  if not user in CMSDIST_PERMISSIONS: return False
  if not match(CMSDIST_PERMISSIONS[user][0], type): return False
  if branch:
    reg = CMSDIST_PERMISSIONS[user][2]
    if reg and match(reg,branch): return False
    reg = CMSDIST_PERMISSIONS[user][1]
    if not match(reg,branch): return False
  return True

def isValidWebHook(payload):
  if (not payload['repository']['full_name'] in ['cms-sw/cmsdist']): return False
  if (not payload['comment']['user']['login'] in CMSDIST_PERMISSIONS.keys()): return False
  comment_lines = [ l.strip() for l in payload['comment']['body'].encode("ascii", "ignore").split("\n") if l.strip() ][0:1]
  if (not comment_lines) or (not getCommentCommand(comment_lines[0])): return False
  return True

USERS_TO_TRIGGER_HOOKS = set(CMSDIST_PERMISSIONS.keys())

