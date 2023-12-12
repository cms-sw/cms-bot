from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER
from os.path import basename, dirname, abspath

GH_TOKEN = "~/.github-token"
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
CMSBUILD_USER = "cmsbuild"
GH_REPO_ORGANIZATION = GH_CMSSW_ORGANIZATION
GH_REPO_NAME = "cms-docker"
GH_REPO_FULLNAME = GH_REPO_ORGANIZATION + "/" + GH_REPO_NAME
JENKINS_SERVER = "http://cmsjenkins02.cern.ch:8080/cms-jenkins"
IGNORE_ISSUES = []
ADD_WEB_HOOK = True
VALID_WEB_HOOKS = [".+"]
