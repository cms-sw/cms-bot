import importlib
import json
import os
import re
import sys

import pytest

from github_utils import api_rate_limits
from . import Framework


class TestNewPullRequest(Framework.TestCase):
    def setUp(self):
        super().setUp()
        self.actionDataFolder = "PRActionData"
        if not os.path.exists(self.actionDataFolder):
            os.mkdir(self.actionDataFolder)
        sys.path.insert(
            0,
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../", "repos", "iarspider_cmssw", "cmssw")
            ),
        )
        if "repo_config" in sys.modules:
            importlib.reload(sys.modules["repo_config"])
            importlib.reload(sys.modules["milestones"])
            importlib.reload(sys.modules["releases"])
            importlib.reload(sys.modules["categories"])

        self.repo_config = sys.modules["repo_config"]
        assert "iarspider_cmssw" in self.repo_config.__file__

    def test_new_pr_dryrun(self):
        from process_pr import process_pr

        prId = 12
        repo = self.g.get_repo("iarspider-cmssw/cmssw")
        res = process_pr(
            self.repo_config,
            self.g,
            repo,
            repo.get_issue(prId),
            True,
            self.repo_config.CMSBUILD_USER,
        )

        fileName = os.path.join(
            self.actionDataFolder,
            "{0}.{1}.json".format(self.__class__.__name__, sys._getframe().f_code.co_name),
        )

        if self.recordMode:
            with open(fileName, "w") as f:
                json.dump(res, f)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)
