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
REPO_HOOK_MAP.append(["cms-sw/cmssdt-ib", ["Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-sw/cmssdt-web", ["Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-sw/cms-bot", ["Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-sw/cms-docker", ["Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-sw/cmssw",   ["Jenkins_Github_Hook", "Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append(["cms-sw/cmsdist", ["Jenkins_Github_Hook", "Jenkins_Github_Hook_Push"]])
REPO_HOOK_MAP.append([".+", ["Jenkins_Github_Hook"]])

