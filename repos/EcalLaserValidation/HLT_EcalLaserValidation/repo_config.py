from cms_static import GH_CMSSW_ORGANIZATION,GH_CMSSW_REPO,CMSBUILD_GH_USER
from os.path import basename,dirname,abspath
GH_TOKEN="~/.github-token-cmsbot"
GH_TOKEN_READONLY="~/.github-token-readonly"
CONFIG_DIR=dirname(abspath(__file__))
CMSBUILD_USER="cmsbot"
GH_REPO_ORGANIZATION="EcalLaserValidation"
GH_REPO_NAME="HLT_EcalLaserValidation"
GH_REPO_FULLNAME=GH_REPO_ORGANIZATION+"/"+GH_REPO_NAME
CREATE_EXTERNAL_ISSUE=False
JENKINS_SERVER="http://cmsjenkins05.cern.ch:8080/cms-jenkins"
GITHUB_WEBHOOK_TOKEN='U2FsdGVkX18uyTkiQtIOYUfVj2PQLV34u5hQAbfNhl8='
ADD_LABELS=True
ADD_WEB_HOOK=False
IGNORE_ISSUES = []
def file2Package(filename): return GH_REPO_NAME
