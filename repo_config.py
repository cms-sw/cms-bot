from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER, get_jenkins
from os.path import dirname, abspath

GH_TOKEN = "~/.github-token"
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
CMSBUILD_USER = CMSBUILD_GH_USER
GH_REPO_ORGANIZATION = GH_CMSSW_ORGANIZATION
CREATE_EXTERNAL_ISSUE = True
CHECK_DPG_POG = True
NONBLOCKING_LABELS = True
JENKINS_SERVER = get_jenkins("jenkins")
IGNORE_ISSUES = {
    GH_CMSSW_ORGANIZATION + "/" + GH_CMSSW_REPO: [12368],
}
