# A ridicously long mapping for categories. Good enough for now.
from cms_static import GH_CMSDIST_REPO as gh_cmsdist
from cms_static import GH_CMSSW_ORGANIZATION as gh_user
from cms_static import GH_CMSSW_REPO as gh_cmssw
from categories_map import CMSSW_CATEGORIES, CMSSW_LABELS
from repo_config import CMSBUILD_USER
from releases import SPECIAL_RELEASE_MANAGERS

authors = {}
# Any Githib user whose comments/requests should be ignored
GITHUB_BLACKLIST_AUTHORS = []
# CMS Offline Release Planning managers
CMSSW_ORP = ["sextonkennedy", "mandrenguyen", "ftenchini"]
# CMS-SDT members who has admin rights to various github organizations and repositories.
# They are also reposionsible to sign for externals
CMS_SDT = ["iarspider", "smuzaffar", "akritkbehera"]
# List of gh users who can approve a release build request
APPROVE_BUILD_RELEASE = list(set(["smuzaffar"] + CMSSW_ORP + SPECIAL_RELEASE_MANAGERS))
# List of gh users who can request to build a release.
REQUEST_BUILD_RELEASE = APPROVE_BUILD_RELEASE
# List og gh users who are allowed to trigger Pull Request testing
TRIGGER_PR_TESTS = list(
    set(
        [
            "felicepantaleo",
            "rovere",
            "lgray",
            "bsunanda",
            "VinInn",
            "kpedro88",
            "makortel",
            "wddgit",
            "mtosi",
            "gpetruc",
            "gartung",
            "nsmith-",
            "mmusich",
            "Sam-Harper",
            "sroychow",
            "silviodonato",
            "slava77",
        ]
        + REQUEST_BUILD_RELEASE
        + [a for a in authors if authors[a] > 10 and not a in GITHUB_BLACKLIST_AUTHORS]
    )
)
# List of on additional release managers
PR_HOLD_MANAGERS = ["kpedro88"]

COMMON_CATEGORIES = ["orp", "tests", "code-checks"]
EXTERNAL_CATEGORIES = ["externals"]
EXTERNAL_REPOS = ["cms-data", "cms-externals", gh_user]

CMSSW_REPOS = [gh_user + "/" + gh_cmssw]
CMSDIST_REPOS = [gh_user + "/" + gh_cmsdist]
CMSSW_ISSUES_TRACKERS = list(set(CMSSW_ORP + ["smuzaffar", "Dr15Jones", "makortel"]))
COMPARISON_MISSING_MAP = ["slava77"]

# CMS L2's and the CMSSW categories they are responsible for. They can also request to start pull requests testing
CMSSW_L2 = {
    "Dr15Jones": ["core", "visualization", "geometry"],
    "Martin-Grunewald": ["hlt"],
    "mmusich": ["hlt"],
    "AdrianoDee": ["pdmv"],
    "antoniovagnerini": ["pdmv"],
    "DickyChant": ["pdmv"],
    "miquork": ["pdmv", "jetmet-pog"],
    "alja": ["visualization"],
    "civanch": ["simulation", "geometry", "fastsim"],
    "bsunanda": ["geometry"],
    "davidlange6": ["operations"],
    "emeschi": ["daq"],
    "hqucms": ["xpog"],
    "ftorrresd": ["xpog"],
    "fwyzard": ["heterogeneous"],
    "jfernan2": ["reconstruction"],
    "makortel": ["heterogeneous", "core", "visualization", "geometry"],
    "mandrenguyen": ["reconstruction", "operations"],
    "mdhildreth": ["simulation", "geometry", "fastsim"],
    "mkirsano": ["generators"],
    "sensrcn": ["generators"],
    "lviliani": ["generators"],
    "theofil": ["generators"],
    "ftenchini": ["operations"],
    "BenjaminRS": ["l1"],
    "quinnanm": ["l1"],
    "rseidita": ["dqm"],
    "ctarricone": ["dqm"],
    "smorovic": ["daq"],
    "smuzaffar": ["core"],
    "srimanob": ["upgrade"],
    "subirsarkar": ["upgrade"],
    "Moanwar": ["upgrade"],
    "ssekmen": ["fastsim"],
    "francescobrivio": ["db"],
    "tvami": ["analysis"],
    "atpathak": ["alca", "db"],
    "perrotta": ["alca", "db"],
    "arunhep": ["alca", "db"],
    "kpedro88": ["simulation", "geometry", "fastsim"],
    CMSBUILD_USER: ["tests"],
    # dpgs
    "mdelcourt": ["trk-dpg"],
    "henriettepetersen": ["trk-dpg"],
    "bmarzocc": ["ecal-dpg"],
    "thomreis": ["ecal-dpg"],
    "wang-hui": ["hcal-dpg"],
    "jhakala": ["hcal-dpg"],
    "abdoulline": ["hcal-dpg"],
    "igv4321": ["hcal-dpg"],
    "mileva": ["muon-dpg"],
    "battibass": ["muon-dpg", "dt-dpg"],
    "fcavallo": ["dt-dpg"],
    "namapane": ["dt-dpg"],
    "ptcox": ["csc-dpg"],
    "jhgoh": ["rpc-dpg"],
    "andresib": ["rpc-dpg"],
    "Pavlov": ["rpc-dpg"],
    "kamon": ["gem-dpg"],
    "jshlee": ["gem-dpg"],
    "watson-ij": ["gem-dpg"],
    "fabferro": ["ctpps-dpg"],
    "jan-kaspar": ["ctpps-dpg"],
    "vavati": ["ctpps-dpg"],
    "rovere": ["hgcal-dpg"],
    "cseez": ["hgcal-dpg"],
    "pfs": ["hgcal-dpg"],
    "felicepantaleo": ["hgcal-dpg"],
    "fabiocos": ["mtd-dpg", "operations"],
    "martinamalberti": ["mtd-dpg"],
    "parbol": ["mtd-dpg"],
    # pogs
    "bellan": ["pf"],
    "kdlong": ["pf"],
    "swagata87": ["pf"],
    "Raffaella07": ["egamma-pog"],
    "RSalvatico": ["egamma-pog"],
    "kirschen": ["jetmet-pog"],
    "alkaloge": ["jetmet-pog"],
    "knollejo": ["lumi-pog"],
    "cschwick": ["lumi-pog"],
    "bonanomi": ["muon-pog"],
    "Fedespring": ["muon-pog"],
    "SWuchterl": ["btv-pog"],
    "mondalspandan": ["btv-pog"],
    "AndreaBellora": ["proton-pog"],
    "forthommel": ["proton-pog"],
    "cardinia": ["tau-pog"],
    "IzaakWN": ["tau-pog"],
    "mbluj": ["tau-pog"],
    "mmasciov": ["tracking-pog"],
    "elusian": ["tracking-pog"],
    # PPD
    "abenecke": ["ppd"],
    "vlimant": ["ppd"],
    "nothingface0": ["dqm"],
    "gabrielmscampos": ["dqm"],
    # ML
    "valsdav": ["ml", "egamma-pog"],
    "y19y19": ["ml"],
}

# Automatically sign these categories if tests are passed
CATS_TO_APPROVE_ON_TEST = ["operations"]

# All CMS_SDT members can sign externals ( e.g Pull Requests in cms-sw/cmsdist , cms-data and cms-externals
for user in CMS_SDT:
    if user not in CMSSW_L2:
        CMSSW_L2[user] = ["externals"]
    elif not "externals" in CMSSW_L2[user]:
        CMSSW_L2[user].append("externals")

# All CMSSW L1 can sign for ORP
for user in CMSSW_ORP:
    if user not in CMSSW_L2:
        CMSSW_L2[user] = ["orp"]
    else:
        CMSSW_L2[user].append("orp")

USERS_TO_TRIGGER_HOOKS = set(TRIGGER_PR_TESTS + CMSSW_ISSUES_TRACKERS + list(CMSSW_L2.keys()))
CMS_REPOS = set(CMSDIST_REPOS + CMSSW_REPOS + EXTERNAL_REPOS)

for user in CMSSW_L2:
    for cat in CMSSW_L2[user]:
        if cat not in CMSSW_CATEGORIES:
            CMSSW_CATEGORIES[cat] = []


def external_to_package(repo_fullname):
    org, repo = repo_fullname.split("/", 1)
    if org == "cms-data":
        return repo.replace("-", "/")
    return ""


# extra labels which bot cn add via 'type label' comment
def get_dpg_pog():
    groups = ["pf", "l1t", "castor"]
    for user in CMSSW_L2:
        for cat in CMSSW_L2[user]:
            if "-" not in cat:
                continue
            grp, ctype = cat.split("-", 1)
            if ctype in ["pog", "dpg"]:
                groups.append(grp)
    return list(set(groups))
