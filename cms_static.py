GH_CMSSW_ORGANIZATION = 'cms-sw'
GH_CMSSW_REPO    = 'cmssw'
GH_CMSDIST_REPO  = 'cmsdist'
BUILD_REL        = '^[Bb]uild[ ]+(CMSSW_[^ ]+)'
NEW_ISSUE_PREFIX = 'A new Issue was created by '
NEW_PR_PREFIX    = 'A new Pull Request was created by '
ISSUE_SEEN_MSG   = '^A new (Pull Request|Issue) was created by '
VALID_CMSDIST_BRANCHES = "^IB/CMSSW_.+$"
CMSDIST_REPO_NAME = GH_CMSSW_ORGANIZATION+"/"+GH_CMSDIST_REPO
CMSSW_REPO_NAME = GH_CMSSW_ORGANIZATION+"/"+GH_CMSSW_REPO

CMSBOT_IGNORE_MSG = "^<cmsbot></cmsbot>.+"
GITHUB_IGNORE_ISSUES = {
  CMSSW_REPO_NAME : [12368],
}
