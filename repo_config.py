from cms_static import GH_CMSSW_ORGANIZATION,GH_CMSSW_REPO,CMSBUILD_GH_USER
from os.path import basename,dirname,abspath
GH_TOKEN="~/.github-token"
GH_TOKEN_READONLY="~/.github-token-readonly"
CONFIG_DIR=dirname(abspath(__file__))
CMSBUILD_USER=CMSBUILD_GH_USER
GH_REPO_ORGANIZATION=GH_CMSSW_ORGANIZATION
CREAT_EXTERNAL_ISSUE=True
IGNORE_ISSUES = {
  GH_CMSSW_ORGANIZATION+"/"+GH_CMSSW_REPO : [12368],
}
def file2Package(filename): return "/".join(filename.split("/", 2)[0:2])
