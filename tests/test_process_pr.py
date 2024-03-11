import importlib
import json
import os
import re
import sys
import traceback

import pytest

from github_utils import api_rate_limits
from . import Framework
from .Framework import readLine


class TestProcessPr(Framework.TestCase):
    @staticmethod
    def compareActions(res_, expected_):
        res = {json.dumps(x, sort_keys=True) for x in res_}
        expected = {json.dumps(x, sort_keys=True) for x in expected_}

        if res.symmetric_difference(expected):
            for itm in res - expected:
                print("New action", itm)

            for itm in expected - res:
                print("Missing action", itm)

            pytest.fail("Actions mismatch")

    def __openEventFile(self, mode):
        fileName = ""
        for (_, _, functionName, _) in traceback.extract_stack():
            if (
                functionName.startswith("test")
                # or functionName == "setUp"
                # or functionName == "tearDown"
            ):
                if (
                    functionName != "test"
                ):  # because in class Hook(Framework.TestCase), method testTest calls Hook.test
                    fileName = os.path.join(
                        self.actionDataFolder,
                        f"{self.__class__.__name__}.{functionName}.json",
                    )
        if not fileName:
            raise RuntimeError("Could not determine event file name!")

        if fileName != self.__eventFileName:
            self.__closeEventReplayFileIfNeeded()
            self.__eventFileName = fileName
            self.__eventFile = open(self.__eventFileName, mode, encoding="utf-8")
        return self.__eventFile

    def __closeEventReplayFileIfNeeded(self):
        if self.__eventFile is not None:
            if (
                not self.recordMode
            ):  # pragma no branch (Branch useful only when recording new tests, not used during automated tests)
                self.assertEqual(readLine(self.__eventFile), "")
            self.__eventFile.close()

    def setUp(self):
        super().setUp()
        prId = 15

        self.__eventFileName = ""
        self.__eventFile = None

        self.repo = self.g.get_repo("iarspider-cmssw/cmssw")
        self.issue = self.repo.get_issue(prId)

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

    def runTest(self):
        from process_pr import process_pr

        if self.recordMode:
            self.__openEventFile("w")
            self.replayData = None
        else:
            f = self.__openEventFile("r")
            self.replayData = json.load(f)

        self.processPrData = process_pr(
            self.repo_config,
            self.g,
            self.repo,
            self.issue,
            True,
            self.repo_config.CMSBUILD_USER,
        )
        self.checkOrSaveTest()
        self.__closeEventReplayFileIfNeeded()

    def checkOrSaveTest(self):
        if self.recordMode:
            json.dump(self.processPrData, self.__eventFile, indent=4)
        else:
            TestProcessPr.compareActions(self.processPrData, self.replayData)

    def test_new_pr(self):
        self.runTest()

    def test_code_check_approved(self):
        self.runTest()

    def test_sign_core(self):
        self.runTest()

    def test_partial_reset(self):
        self.runTest()

    def test_reset_signature(self):
        self.runTest()

    def test_revert_dqm(self):
        self.runTest()

    def test_start_tests(self):
        self.runTest()

    def test_tests_rejected(self):
        self.runTest()

    def test_tests_passed(self):
        self.runTest()

    def test_hold(self):
        self.runTest()

    def test_unhold(self):
        self.runTest()

    def test_assign(self):
        self.runTest()

    def test_unassign(self):
        self.runTest()

    def test_test_params(self):
        self.runTest()

    def test_run_test_params(self):
        self.runTest()

    def test_abort(self):
        self.runTest()

    def test_close(self):
        self.runTest()

    def test_reopen(self):
        self.runTest()

    def test_invalid_type(self):
        self.runTest()

    def test_valid_type(self):
        self.runTest()

    def test_clean_squash(self):
        self.runTest()

    def test_dirty_squash(self):
        self.runTest()

    def test_sign_reject(self):
        self.runTest()

    # Not yet implemented
    def test_many_commits(self):
        self.runTest()

    # Not yet implemented
    def test_many_commits_ok(self):
        self.runTest()

    # Not yet implemented
    def test_too_many_commits(self):
        self.runTest()

    def test_future_commit(self):
        self.runTest()

    def test_backdated_commit(self):
        self.runTest()
