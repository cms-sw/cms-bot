from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER, get_jenkins
from os.path import basename, dirname, abspath

GH_TOKEN = "~/.github-token-cmsbot"
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
CMSBUILD_USER = "cmsbot"
GH_REPO_ORGANIZATION = "HcalConditionsAutomatization"
GH_REPO_NAME = "ConditionsValidation"
GH_REPO_FULLNAME = GH_REPO_ORGANIZATION + "/" + GH_REPO_NAME
CREATE_EXTERNAL_ISSUE = False
JENKINS_SERVER = get_jenkins("cms-jenkins")
ADD_LABELS = False
ADD_WEB_HOOK = True
JENKINS_UPLOAD_DIRECTORY = "HcalConditionsAutomatization/ConditionsValidation"
JENKINS_NOTIFICATION_EMAIL = ""
OPEN_ISSUE_FOR_PUSH_TESTS = True
IGNORE_ISSUES = []
# Valid Web hooks
VALID_WEB_HOOKS = ["push"]
# Set the Jenkins slave label is your tests needs special machines to run.
JENKINS_SLAVE_LABEL = "lxplus"


def file2Package(filename):
    return GH_REPO_NAME
