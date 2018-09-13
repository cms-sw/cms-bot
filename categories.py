# A ridicously long mapping for categories. Good enough for now.
import re
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from categories_map import CMSSW_CATEGORIES
from repo_config import CMSBUILD_USER

authors = {}
GITHUB_BLACKLIST_AUTHORS = []
CMSSW_L1 = ["davidlange6", "fabiocos", "kpedro88"]
APPROVE_BUILD_RELEASE =  list(set([ "smuzaffar", "slava77" ] + CMSSW_L1))
REQUEST_BUILD_RELEASE = APPROVE_BUILD_RELEASE
TRIGGER_PR_TESTS = list(set([ "lgray", "bsunanda", "VinInn", "kpedro88", "makortel", "wddgit", "mtosi", "gpetruc"] + REQUEST_BUILD_RELEASE + [ a for a in authors if authors[a]>10 and not a in GITHUB_BLACKLIST_AUTHORS ]))
PR_HOLD_MANAGERS = [ "kpedro88" ]

COMMON_CATEGORIES = [ "orp", "tests", "code-checks" ]
EXTERNAL_CATEGORIES = [ "externals" ]
EXTERNAL_REPOS = [ "cms-data", "cms-externals", gh_user]

CMSSW_REPOS = [ gh_user+"/"+gh_cmssw ]
CMSDIST_REPOS = [ gh_user+"/"+gh_cmsdist ]
CMSSW_ISSUES_TRACKERS = list(set(CMSSW_L1 + [ "smuzaffar", "Dr15Jones" ]))
COMPARISON_MISSING_MAP = [ "slava77" ]

CMSSW_L2 = {
  "Martin-Grunewald": ["hlt"],
  "perrotta": ["reconstruction"],
  "fwyzard": ["hlt"],
  "slava77": ["reconstruction"],
  "civanch": ["simulation", "geometry", "fastsim"],
  "mdhildreth": ["simulation", "geometry", "fastsim"],
  "Dr15Jones": ["core", "visualization", "geometry"],
  "smuzaffar": ["core", "externals"],
  "alja": ["visualization"],
  "ianna": ["geometry"],
  "cvuosalo": ["geometry"],
  "ggovi": ["db"],
  "franzoni": ["operations","alca"],
  "cmsdoxy": ["docs"],
  "mommsen": ["daq"],
  "emeschi": ["daq"],
  "rekovic": ["l1"],
  "thomreis": ["l1"],
  "nsmith-": ["l1"],  
  "lveldere": ["fastsim"],
  "ssekmen": ["fastsim"],
  "perrozzi": ["generators"],
  "efeyazgan": ["generators"],
  "qliphy": ["generators"],
  "alberto-sanchez": ["generators"],
  "davidlange6": ["operations"],
  "fabiocos": ["operations"],
  "schneiml" : ["dqm"],
  "kmaeshima" : ["dqm"],
  "andrius-k" : ["dqm"],
  "prebello" : ["pdmv"],
  "pgunnell" : ["pdmv"],
  "zhenhu" : ["pdmv"],
  "monttj" : ["analysis"],
  "pohsun" : ["alca"],
  "tocheng" : ["alca"],
  "kpedro88" : ["upgrade"],
  "mrodozov" : ["externals"],
  "gudrutis" : ["externals"],
  "lpernie" : ["alca"],
  "jfernan2": ["dqm"],
  "arizzi": ["analysis"],
  "gpetruc": ["analysis"],
  CMSBUILD_USER: ["tests", "code-checks" ],
}

USERS_TO_TRIGGER_HOOKS = set(TRIGGER_PR_TESTS + CMSSW_ISSUES_TRACKERS + CMSSW_L2.keys())
CMS_REPOS = set(CMSDIST_REPOS + CMSSW_REPOS + EXTERNAL_REPOS)
from datetime import datetime
COMMENT_CONVERSION = {}
COMMENT_CONVERSION['kpedro88']={'comments_before': datetime.strptime('2018-07-13','%Y-%m-%d'), 'comments':[('+1', '+upgrade')]}
