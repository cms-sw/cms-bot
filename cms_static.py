GH_CMSSW_ORGANIZATION = 'cms-sw'
GH_CMSSW_REPO    = 'cmssw'
GH_CMSDIST_REPO  = 'cmsdist'
BUILD_REL        = '^[Bb]uild[ ]+(CMSSW_[^ ]+)'
NEW_ISSUE_PREFIX = 'A new Issue was created by '
NEW_PR_PREFIX    = 'A new Pull Request was created by '
ISSUE_SEEN_MSG   = '^A new (Pull Request|Issue) was created by '
VALID_CMSDIST_BRANCHES = "^IB/CMSSW_.+$"
BACKPORT_STR     ="- Backported from #"
CMSBUILD_GH_USER ="cmsbuild"
CMSBOT_IGNORE_MSG= "^<cmsbot></cmsbot>.+"
VALID_CMS_SW_REPOS_FOR_TESTS = ["cmssw", "cmsdist", "cms-bot","root", "cmssw-config",
                      "pkgtools", "SCRAM", "cmssw-osenv", "cms-git-tools",
                      "cms-common","cms_oracleocci_abi_hack","siteconf"]
