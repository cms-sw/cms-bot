GH_CMSSW_ORGANIZATION = "cms-sw"
GH_CMSSW_REPO = "cmssw"
GH_CMSDIST_REPO = "cmsdist"
BUILD_REL = "^[Bb]uild[ ]+(CMSSW_[^ ]+)"
CREATE_REPO = "^[Cc]reate[ ]+repository[ ]+([A-Z][0-9A-Za-z]+)[-/]([a-zA-Z][0-9A-Za-z]+)"
NEW_ISSUE_PREFIX = "A new Issue was created by "
NEW_PR_PREFIX = "A new Pull Request was created by "
ISSUE_SEEN_MSG = "^A new (Pull Request|Issue) was created by "
VALID_CMSDIST_BRANCHES = "^IB/CMSSW_.+$"
BACKPORT_STR = "- Backported from #"
CMSBUILD_GH_USER = "cmsbuild"
CMSBOT_IGNORE_MSG = "<cmsbot>\\s*</cmsbot>"
CMSBOT_NO_NOTIFY_MSG = "<notify>\\s*</notify>"
CMSBOT_TECHNICAL_MSG = "cms-bot internal usage"
JENKINS_HOST = "cmsjenkins04"
CMS_JENKINS_HOST = "cmsjenkins02"
DMWM_JENKINS_HOST = "cmsjenkins11"
VALID_CMS_SW_REPOS_FOR_TESTS = [
    "cmssw",
    "cmsdist",
    "cmssdt-ib",
    "cmssdt-web",
    "cms-bot",
    "root",
    "cmssw-config",
    "pkgtools",
    "SCRAM",
    "cmssw-osenv",
    "cms-git-tools",
    "cms-common",
    "cms_oracleocci_abi_hack",
    "cms-docker",
    "siteconf",
]


def get_jenkins(prefix):
    jhost = JENKINS_HOST
    if prefix == "cms-jenkins":
        jhost = CMS_JENKINS_HOST
    elif prefix == "dmwm-jenkins":
        jhost = DMWM_JENKINS_HOST
    return "http://%s.cern.ch:8080/%s" % (jhost, prefix)
