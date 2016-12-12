#cmsdist/comp rules
from re import match,IGNORECASE

#Merge format: "user" : [ regexp for valid commands, regexp of allowed branches, regexp of not allowed branches ]
CMSSW_BRANCHES   = "^IB/CMSSW_.+$"
COMP_BRANCHES    = ".+"
WMAGENT_BRANCHES = "^comp_gcc493$"
CMSDIST_PERMISSIONS = {
  "BrunoCoimbra"   : [ ".+", COMP_BRANCHES ,CMSSW_BRANCHES ],
  "h4d4"           : [ ".+", COMP_BRANCHES ,CMSSW_BRANCHES ],
  "amaltaro"       : [ ".+", WMAGENT_BRANCHES ,CMSSW_BRANCHES ],
  "ticoann"        : [ ".+", WMAGENT_BRANCHES ,CMSSW_BRANCHES ],
}

VALID_COMMENTS = {
  "^(please(\s*,|)\s+|)merge$"    : "merge",
  "^(please(\s*,|)\s+|)close$"    : "close",
  "^(please(\s*,|)\s+|)(re|)open$": "open",
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
    if match(CMSDIST_PERMISSIONS[user][2],branch): return False
    if not match(CMSDIST_PERMISSIONS[user][1],branch): return False
  return True

USERS_TO_TRIGGER_HOOKS = set(CMSDIST_PERMISSIONS.keys())

