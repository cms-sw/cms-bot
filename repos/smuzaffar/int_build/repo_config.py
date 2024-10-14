from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER, get_jenkins
from os.path import basename, dirname, abspath

GH_TOKEN = "~/.github-token-cmsbot"
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
CMSBUILD_USER = "cmsbot"
GH_REPO_ORGANIZATION = basename(dirname(CONFIG_DIR))
GH_REPO_FULLNAME = "smuzaffar/int-build"
CREATE_EXTERNAL_ISSUE = False
JENKINS_SERVER = get_jenkins("cms-jenkins")
GITHUB_WEBHOOK_TOKEN = "U2FsdGVkX1+GEHdp/Cmu73+ctvrzSGXc9OvL+8bZyjOe6ZPkqr/GIPgpJHiEp+hR"
ADD_LABELS = False
ADD_WEB_HOOK = False
IGNORE_ISSUES = []


def file2Package(filename):
    return GH_REPO_ORGANIZATION
