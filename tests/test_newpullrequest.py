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
                os.path.join(os.path.dirname(__file__), "..", "repos", "iarspider_cmssw", "cmssw")
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

        prId = 13
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

    def test_code_check_approved(self):
        from process_pr import process_pr

        prId = 13
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

    def test_sign_core(self):
        from process_pr import process_pr

        prId = 13
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

    def test_partial_reset(self):
        from process_pr import process_pr

        prId = 13
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

    def test_reset_signature(self):
        from process_pr import process_pr

        prId = 13
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

    def test_revert_dqm(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_start_tests(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_tests_rejected(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_tests_passed(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_fully_signed(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_hold(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_unhold(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_assign(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_unassign(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_test_params(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_run_test_params(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_abort(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_close(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_reopen(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)

    def test_invalid_type(self):
        from process_pr import process_pr

        prId = 13
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
                json.dump(res, f, indent=4)
        else:
            with open(fileName, "r") as f:
                expected = json.load(f)

            TestNewPullRequest.compareActions(res, expected)
