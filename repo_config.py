import datetime

from cms_static import GH_CMSSW_ORGANIZATION, GH_CMSSW_REPO, CMSBUILD_GH_USER, get_jenkins
from os.path import dirname, abspath
import os

try:
    from datetime import timezone

    utc = timezone.utc
except ImportError:

    class UTC(datetime.tzinfo):
        def utcoffset(self, dt):
            return datetime.timedelta(0)

        def tzname(self, dt):
            return "UTC"

        def dst(self, dt):
            return datetime.timedelta(0)

    utc = UTC()

GH_TOKEN = os.getenv("GH_TOKEN_FILE", "~/.github-token")
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
LEGACY_CATEGORIES = {"upgrade": datetime.datetime(2025, 10, 10, 0, 0, tzinfo=utc)}

# Signatures required to trigger tests
PRE_CHECKS = [(0, "code-format")]
# Signatures required to merge PR
EXTRA_CHECKS = [(0, "orp")]
