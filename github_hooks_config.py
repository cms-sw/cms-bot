GITHUB_HOOKS = {}
GITHUB_HOOKS["Jenkins_Github_Hook"] = {
  "active":True,
  "events":  ["issues","pull_request","issue_comment"],
  "config": {
    "url": "https://cmssdt.cern.ch/SDT/cgi-bin/github_webhook",
    "content_type":"json"
  }
}

GITHUB_HOOKS["Jenkins_Github_Hook_Push"] = {
  "active":True,
  "events":  ["push"],
  "config": {
    "url": "https://cmssdt.cern.ch/SDT/cgi-bin/github_webhook?push",
    "content_type":"json"
  }
}

#First repository name matches wins
REPO_HOOK_MAP = []
REPO_HOOK_MAP.append(["cms-sw/cms-sw.github.io", []])
REPO_HOOK_MAP.append(["cms-sw/cms-prs", []])
REPO_HOOK_MAP.append(["cms-sw/.+", ["Jenkins_Github_Hook","Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-data/.+", ["Jenkins_Github_Hook","Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-externals/.+", ["Jenkins_Github_Hook","Jenkins_Github_Hook_Push"]])

def get_repository_hooks(repo_name, hook=""):
  import re
  hooks = {}
  for r in REPO_HOOK_MAP:
    if re.match(r[0],repo_name):
      if not hook:
        for h in r[1]: hooks[h]=GITHUB_HOOKS[h]
      elif hook in r[1]:
        hooks[hook] = GITHUB_HOOKS[hook]
      break
  return hooks

