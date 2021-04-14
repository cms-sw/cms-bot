# A ridicously long mapping for categories. Good enough for now.
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from categories_map import CMSSW_CATEGORIES
from repo_config import CMSBUILD_USER
from releases import SPECIAL_RELEASE_MANAGERS

authors = {}
GITHUB_BLACKLIST_AUTHORS = []
CMSSW_L1 = ["dpiparo", "silviodonato","qliphy"]
APPROVE_BUILD_RELEASE =  list(set([ "smuzaffar"] + CMSSW_L1 + SPECIAL_RELEASE_MANAGERS))
REQUEST_BUILD_RELEASE = APPROVE_BUILD_RELEASE
TRIGGER_PR_TESTS = list(set([ "felicepantaleo", "rovere", "lgray", "bsunanda", "VinInn", "kpedro88", "makortel", "wddgit", "mtosi", "gpetruc", "gartung", "nsmith-","mmusich","Sam-Harper"] + REQUEST_BUILD_RELEASE + [ a for a in authors if authors[a]>10 and not a in GITHUB_BLACKLIST_AUTHORS ]))
PR_HOLD_MANAGERS = [ "kpedro88" ]

COMMON_CATEGORIES = [ "orp", "tests", "code-checks" ]
EXTERNAL_CATEGORIES = [ "externals" ]
EXTERNAL_REPOS = [ "cms-data", "cms-externals", gh_user]

CMSSW_REPOS = [ gh_user+"/"+gh_cmssw ]
CMSDIST_REPOS = [ gh_user+"/"+gh_cmsdist ]
CMSSW_ISSUES_TRACKERS = list(set(CMSSW_L1 + [ "smuzaffar", "Dr15Jones", "makortel" ]))
COMPARISON_MISSING_MAP = [ "slava77" ]

CMSSW_L2 = {
  "Dr15Jones":        ["core", "visualization", "geometry"],
  "Martin-Grunewald": ["hlt"],
  "ahmad3213":        ["dqm"],
  "alberto-sanchez":  ["generators"],
  "agrohsje":         ["generators"],
  "alja":             ["visualization"],
  "andrius-k":        ["dqm"],
  "chayanit":         ["pdmv"],
  "civanch":          ["simulation", "geometry", "fastsim"],
  "cvuosalo":         ["geometry"],
  "davidlange6":      ["operations"],
  "emeschi":          ["daq"],
  "ErnestaP":         ["dqm"],
  "fabiocos":         ["operations","mtd-dpg"],
  "fgolf":            ["xpog"],
  "franzoni":         ["operations"],
  "fwyzard":          ["heterogeneous", "hlt"],
  "ggovi":            ["db"],
  "gouskos":          ["xpog"],
  "GurpreetSinghChahal":  ["generators"],
  "ianna":            ["geometry"],
  "jfernan2":         ["dqm"],
  "cecilecaillol":    ["l1"],
  "jordan-martins":   ["pdmv"],
  "jpata":            ["reconstruction"],
  "kmaeshima":        ["dqm"],
  "kpedro88":         ["upgrade"],
  "lveldere":         ["fastsim"],
  "makortel":         ["heterogeneous", "core", "visualization", "geometry"],
  "mariadalfonso":    ["xpog"],
  "mdhildreth":       ["simulation", "geometry", "fastsim"],
  "mkirsano":         ["generators"],   
  "mrodozov":         ["externals"],
  "perrotta":         ["reconstruction"],
  "pohsun":           ["alca"],
  "qliphy":           ["operations"],
  "rekovic":          ["l1"],
  "rvenditti":        ["dqm"],
  "santocch":         ["analysis"],
  "sbein":            ["fastsim"],
  "SiewYan":          ["generators"], 
  "silviodonato":     ["operations"],
  "slava77":          ["reconstruction"],
  "smorovic":         ["daq"],
  "smuzaffar":        ["core", "externals"],
  "srimanob":         ["upgrade"],
  "ssekmen":          ["fastsim"],
  "tlampen":          ["alca"],
  "wajidalikhan":     ["pdmv"],
  "christopheralanwest": ["alca"],
  "yuanchao":         ["alca"],
  "francescobrivio":  ["alca"],
  "malbouis":         ["alca"],
  CMSBUILD_USER:      ["tests" ],
  # dpgs
  "tsusa":            ["trk-dpg"],
  "mmusich":          ["trk-dpg"],
  "thomreis":         ["ecal-dpg"],
  "mseidel42":        ["hcal-dpg"],
  "georgia14":        ["hcal-dpg"],
  "mileva":           ["muon-dpg"],
  "battibass":        ["dt-dpg"],
  "fcavallo":         ["dt-dpg"],
  "namapane":         ["dt-dpg"],
  "ptcox":            ["csc-dpg"],
  "jhgoh":            ["rpc-dpg"],
  "andresib":         ["rpc-dpg"],
  "pavlov":           ["rpc-dpg"],
  "kamon":            ["gem-dpg"],
  "jlee":             ["gem-dpg"],
  "fabferro":         ["ctpps-dpg"],
  "jan-kaspar":       ["ctpps-dpg"],
  "vavati":           ["ctpps-dpg"],
  "rovere":           ["hgcal-dpg"],
  "cseez":            ["hgcal-dpg"],
  "parbol":           ["mtd-dpg"],
}

USERS_TO_TRIGGER_HOOKS = set(TRIGGER_PR_TESTS + CMSSW_ISSUES_TRACKERS + list(CMSSW_L2.keys()))
CMS_REPOS = set(CMSDIST_REPOS + CMSSW_REPOS + EXTERNAL_REPOS)
from datetime import datetime
COMMENT_CONVERSION = {}
COMMENT_CONVERSION['kpedro88']={'comments_before': datetime.strptime('2018-07-13','%Y-%m-%d'), 'comments':[('+1', '+upgrade')]}
COMMENT_CONVERSION['qliphy']={'comments_before': datetime.strptime('2020-07-24','%Y-%m-%d'), 'comments':[('+1', '+generators'),('-1', '-generators')]}


def external_to_package(repo_fullname):
  org, repo = repo_fullname.split("/",1)
  if org == "cms-data":
    return repo.replace('-','/')
  return ''
