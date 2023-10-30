# cmsdist/comp rules
from re import match, IGNORECASE

CMSSW_BRANCHES = "^IB/CMSSW_.+$"
ALL_BRANCHES = ".+"
COMP_BRANCHES = "^comp_gcc.+$"
# CMSDIST_PERMISSIONS: format
# gh-user: [command-type, regexp-valid-branch, regexp-invalid-branch, regexp-changed-files-for-merge-command]
CMSDIST_PERMISSIONS = {
    "muhammadimranfarooqi": [".+", ALL_BRANCHES, CMSSW_BRANCHES, ".+"],
    "arooshap": [".+", ALL_BRANCHES, CMSSW_BRANCHES, ".+"],
    "amaltaro": [".+", COMP_BRANCHES, CMSSW_BRANCHES, ".+"],
    "todor-ivanov": [".+", COMP_BRANCHES, CMSSW_BRANCHES, ".+"],
    "belforte": [".+", COMP_BRANCHES, CMSSW_BRANCHES, ".+"],
    "mapellidario": [".+", COMP_BRANCHES, CMSSW_BRANCHES, ".+"],
    "germanfgv": [".+", COMP_BRANCHES, CMSSW_BRANCHES, ".+"],
}

VALID_COMMENTS = {
    "^(please(\s*,|)\s+|)merge$": "merge",
    "^(please(\s*,|)\s+|)close$": "close",
    "^(please(\s*,|)\s+|)(re|)open$": "open",
    "^ping$": "ping",
    "^(please(\s*,|)\s+|)test$": "test",
}


def getCommentCommand(comment):
    comment = comment.strip().lower()
    for regex in VALID_COMMENTS:
        if match(regex, comment, IGNORECASE):
            return VALID_COMMENTS[regex]
    return None


def hasRights(user, branch, type, files=[]):
    if not user in CMSDIST_PERMISSIONS:
        return False
    if not match(CMSDIST_PERMISSIONS[user][0], type):
        return False
    if branch:
        reg = CMSDIST_PERMISSIONS[user][2]
        if reg and match(reg, branch):
            return False
        reg = CMSDIST_PERMISSIONS[user][1]
        if not match(reg, branch):
            return False
        if type == "merge":
            for f in files:
                if not match(CMSDIST_PERMISSIONS[user][3], f):
                    return False
    return True


def isValidWebHook(payload):
    if not payload["repository"]["full_name"] in ["cms-sw/cmsdist"]:
        return False
    if not payload["comment"]["user"]["login"] in CMSDIST_PERMISSIONS.keys():
        return False
    comment_lines = [
        l.strip()
        for l in payload["comment"]["body"].encode("ascii", "ignore").decode().split("\n")
        if l.strip()
    ][0:1]
    if (not comment_lines) or (not getCommentCommand(comment_lines[0])):
        return False
    return True


USERS_TO_TRIGGER_HOOKS = set(CMSDIST_PERMISSIONS.keys())
