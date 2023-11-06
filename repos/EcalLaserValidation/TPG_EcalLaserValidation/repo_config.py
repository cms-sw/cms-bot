from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER
from os.path import basename, dirname, abspath

GH_TOKEN = "~/.github-token"
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
CMSBUILD_USER = "cmsbuild"
GH_REPO_ORGANIZATION = "EcalLaserValidation"
GH_REPO_NAME = "TPG_EcalLaserValidation"
GH_REPO_FULLNAME = GH_REPO_ORGANIZATION + "/" + GH_REPO_NAME
CREATE_EXTERNAL_ISSUE = False
JENKINS_SERVER = "http://cmsjenkins02.cern.ch:8080/cms-jenkins"
GITHUB_WEBHOOK_TOKEN = "U2FsdGVkX1+GGHoH9PB4G9rRvEuoKejWnx1zWHOV39VGswFB1rX9s7F3HFdaTtcs"
ADD_LABELS = False
ADD_WEB_HOOK = False
JENKINS_UPLOAD_DIRECTORY = "EcalLaserValidation/TPG_EcalLaserValidation"
JENKINS_NOTIFICATION_EMAIL = ""
OPEN_ISSUE_FOR_PUSH_TESTS = True
IGNORE_ISSUES = []
# Valid Web hooks
VALID_WEB_HOOKS = ["push"]
# Set the Jenkins slave label if your tests needs special machines to run.
JENKINS_SLAVE_LABEL = "slc6 && amd64 && cmsbuild"


def file2Package(filename):
    return GH_REPO_NAME
