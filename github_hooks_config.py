GITHUB_HOOKS = {}
GITHUB_HOOKS["Jenkins_Github_Hook"] = {
  "active":True,
  "events":  ["push","issues","pull_request","issue_comment"],
  "config": {
    "url": "https://cmssdt.cern.ch/SDT/cgi-bin/github_webhook",
    "content_type":"json"
  }
}
