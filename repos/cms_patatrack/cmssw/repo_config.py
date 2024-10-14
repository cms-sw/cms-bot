from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER, get_jenkins
from os.path import basename, dirname, abspath

# GH read/write token: Use default ~/.github-token-cmsbot
GH_TOKEN = "~/.github-token-cmsbot"
# GH readonly token: Use default ~/.github-token-readonly
GH_TOKEN_READONLY = "~/.github-token-readonly"
CONFIG_DIR = dirname(abspath(__file__))
# GH bot user: Use default cmsbot
CMSBUILD_USER = "cmsbot"
GH_REPO_ORGANIZATION = "cms-patatrack"
GH_REPO_FULLNAME = "cms-patatrack/cmssw"
CREATE_EXTERNAL_ISSUE = False
# Jenkins CI server: User default http://cms-jenkins.cern.ch:8080/cms-jenkins
JENKINS_SERVER = get_jenkins("cms-jenkins")
# GH Web hook pass phrase. This is encrypeted used bot keys.
GITHUB_WEBHOOK_TOKEN = """U2FsdGVkX19C9pvh4GUbgDDUy0G9tSJZu7pFoQ0QodGMQtb/h4AFOKPsBxKlORAz
KXg7+k1B6egPueUzlaJ9BA=="""
# Set to True if you want bot to add build/test labels to your repo
ADD_LABELS = True
# Set to True if you want bot to add GH webhooks. cmsbot needs admin rights
ADD_WEB_HOOK = False
# List of issues/pr which bot should ignore
IGNORE_ISSUES = []
# Set the Jenkins slave label is your tests needs special machines to run.
JENKINS_SLAVE_LABEL = "slc7_amd64 && GPU"
# For cmsdist/cmssw repos , set it to False if you do not want to run standard cms pr tests
CMS_STANDARD_TESTS = True
# Map your branches with cmssw branches for tests
# User Branch => CMSSW/CMSDIST Bracnh
CMS_BRANCH_MAP = {
    "CMSSW_10_1_X_Patatrack": "CMSSW_10_1_X",
    "CMSSW_10_2_X_Patatrack": "CMSSW_10_2_X",
}
# Valid Web hooks e.g. '.+' to match all event
VALID_WEB_HOOKS = [".+"]
