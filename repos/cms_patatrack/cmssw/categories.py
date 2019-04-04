from cms_static import GH_CMSSW_REPO as gh_cmssw
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from repo_config import GH_REPO_ORGANIZATION as gh_user
from repo_config import CMSBUILD_USER
from categories_map import CMSSW_CATEGORIES

CMSSW_L1 = []
APPROVE_BUILD_RELEASE =  list(set([  ] + CMSSW_L1))
REQUEST_BUILD_RELEASE = APPROVE_BUILD_RELEASE
TRIGGER_PR_TESTS = list(set(['smuzaffar','felicepantaleo'] + REQUEST_BUILD_RELEASE))
PR_HOLD_MANAGERS = [ ]

COMMON_CATEGORIES = [ "tests", "code-checks" ]
EXTERNAL_CATEGORIES = [ "externals" ]
EXTERNAL_REPOS = []

CMSSW_REPOS = [ gh_user+"/"+gh_cmssw ]
CMSDIST_REPOS = [ gh_user+"/"+gh_cmsdist ]
CMSSW_ISSUES_TRACKERS = list(set(CMSSW_L1))
COMPARISON_MISSING_MAP = []

#github_user:[list of categories]
CMSSW_L2 = {
  CMSBUILD_USER : ["tests", "code-checks" ],
  'fwyzard'     : list(CMSSW_CATEGORIES.keys()),
}

USERS_TO_TRIGGER_HOOKS = set(TRIGGER_PR_TESTS + CMSSW_ISSUES_TRACKERS + list(CMSSW_L2.keys()))
CMS_REPOS = set(CMSDIST_REPOS + CMSSW_REPOS + EXTERNAL_REPOS)
