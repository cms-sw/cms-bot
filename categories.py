# A ridicously long mapping for categories. Good enough for now.
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from categories_map import CMSSW_CATEGORIES
from repo_config import CMSBUILD_USER
from releases import SPECIAL_RELEASE_MANAGERS

authors = {}
GITHUB_BLACKLIST_AUTHORS = []
CMSSW_L1 = ["dpiparo", "qliphy", "perrotta"]
APPROVE_BUILD_RELEASE =  list(set([ "smuzaffar"] + CMSSW_L1 + SPECIAL_RELEASE_MANAGERS))
REQUEST_BUILD_RELEASE = APPROVE_BUILD_RELEASE
TRIGGER_PR_TESTS = list(set([ "felicepantaleo", "rovere", "lgray", "bsunanda", "VinInn", "kpedro88", "makortel", "wddgit", "mtosi", "gpetruc", "gartung", "nsmith-","mmusich","Sam-Harper","sroychow","silviodonato"] + REQUEST_BUILD_RELEASE + [ a for a in authors if authors[a]>10 and not a in GITHUB_BLACKLIST_AUTHORS ]))
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
  "AdrianoDee":       ["upgrade"],
  "ahmad3213":        ["dqm"],
  "alberto-sanchez":  ["generators"],
  "agrohsje":         ["generators"],
  "alja":             ["visualization"],
  "bbilin":           ["pdmv"],
  "civanch":          ["simulation", "geometry", "fastsim"],
  "cvuosalo":         ["geometry"],
  "davidlange6":      ["operations"],
  "emanueleusai":     ["dqm"],
  "emeschi":          ["daq"],
  "fgolf":            ["xpog"],
  "fwyzard":          ["heterogeneous"],
  "ggovi":            ["db"],
  "gouskos":          ["xpog"],
  "GurpreetSinghChahal":  ["generators"],
  "ianna":            ["geometry"],
  "iarspider":        ["externals"],
  "jfernan2":         ["dqm"],
  "cecilecaillol":    ["l1"],
  "clacaputo":        ["reconstruction"],
  "jordan-martins":   ["pdmv"],
  "jpata":            ["reconstruction"],
  "kskovpen":         ["pdmv"],
  "lveldere":         ["fastsim"],
  "makortel":         ["heterogeneous", "core", "visualization", "geometry"],
  "mariadalfonso":    ["xpog"],
  "mdhildreth":       ["simulation", "geometry", "fastsim"],
  "missirol":         ["hlt"],
  "mkirsano":         ["generators"],   
  "ddaina":           ["externals"],
  "perrotta":         ["operations"],
  "pmandrik":         ["dqm"],
  "pbo0":             ["dqm"],
  "qliphy":           ["operations"],
  "epalencia":        ["l1"],
  "rekovic":          ["l1"],
  "rvenditti":        ["dqm"],
  "santocch":         ["analysis"],
  "Saptaparna":       ["generators"],
  "sbein":            ["fastsim"],
  "SiewYan":          ["generators"], 
  "slava77":          ["reconstruction"],
  "smorovic":         ["daq"],
  "smuzaffar":        ["core", "externals"],
  "srimanob":         ["upgrade"],
  "ssekmen":          ["fastsim"],
  "wajidalikhan":     ["pdmv"],
  "yuanchao":         ["alca"],
  "francescobrivio":  ["alca","db"],
  "malbouis":         ["alca","db"],
  "tvami":            ["alca","db"],
  CMSBUILD_USER:      ["tests" ],
  # dpgs
  "tsusa":            ["trk-dpg"],
  "connorpa":         ["trk-dpg"],
  "simonepigazzini":  ["ecal-dpg"],
  "jainshilpi":       ["ecal-dpg"],
  "thomreis":         ["ecal-dpg"],
  "mseidel42":        ["hcal-dpg"],
  "georgia14":        ["hcal-dpg"],
  "igv4321":          ["hcal-dpg"],
  "mileva":           ["muon-dpg"],
  "battibass":        ["muon-dpg","dt-dpg"],
  "fcavallo":         ["dt-dpg"],
  "namapane":         ["dt-dpg"],
  "ptcox":            ["csc-dpg"],
  "jhgoh":            ["rpc-dpg"],
  "andresib":         ["rpc-dpg"],
  "pavlov":           ["rpc-dpg"],
  "kamon":            ["gem-dpg"],
  "jshlee":           ["gem-dpg"],
  "watson-ij":        ["gem-dpg"],
  "fabferro":         ["ctpps-dpg"],
  "jan-kaspar":       ["ctpps-dpg"],
  "vavati":           ["ctpps-dpg"],
  "rovere":           ["hgcal-dpg"],
  "cseez":            ["hgcal-dpg"],
  "pfs":              ["hgcal-dpg"],
  "felicepantaleo":   ["hgcal-dpg"],
  "fabiocos":         ["mtd-dpg", "operations"],
  "parbol":           ["mtd-dpg"],
  # pogs
  "juska":            ["pf"],
  "kdlong":           ["pf"],
  "lfinco":           ["egamma-pog"],
  "swagata87":        ["egamma-pog"],
  "kirschen":         ["jetmet-pog"],
  "camclean":         ["jetmet-pog"],
  "knollejo":         ["lumi-pog"],
  "cschwick":         ["lumi-pog"],
  "gkaratha":         ["muon-pog"],
  "sscruz":           ["muon-pog"],
  "johnalison":       ["btv-pog"],
  "soureek":          ["btv-pog"],
  "michael-pitt":     ["proton-pog"],
  "kshcheli":         ["proton-pog"],
  "kandrosov":        ["tau-pog"],
  "alebihan":         ["tau-pog"],
  "mtosi":            ["tracking-pog"],
  "vmariani":         ["tracking-pog"],
  "mmusich":          ["tracking-pog","trk-dpg"],
}

for user in CMSSW_L1:
  if user not in CMSSW_L2: CMSSW_L2[user] = ['orp']
  else: CMSSW_L2[user].append('orp')

USERS_TO_TRIGGER_HOOKS = set(TRIGGER_PR_TESTS + CMSSW_ISSUES_TRACKERS + list(CMSSW_L2.keys()))
CMS_REPOS = set(CMSDIST_REPOS + CMSSW_REPOS + EXTERNAL_REPOS)
from datetime import datetime
COMMENT_CONVERSION = {}
COMMENT_CONVERSION['kpedro88']={'comments_before': datetime.strptime('2018-07-13','%Y-%m-%d'), 'comments':[('+1', '+upgrade')]}
COMMENT_CONVERSION['qliphy']={'comments_before': datetime.strptime('2020-07-24','%Y-%m-%d'), 'comments':[('+1', '+generators'),('-1', '-generators')]}

for user in CMSSW_L2:
  for cat in CMSSW_L2[user]:
    if cat not in CMSSW_CATEGORIES:
      CMSSW_CATEGORIES[cat] = []

def external_to_package(repo_fullname):
  org, repo = repo_fullname.split("/",1)
  if org == "cms-data":
    return repo.replace('-','/')
  return ''
