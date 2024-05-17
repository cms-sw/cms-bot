import importlib
import json
import os
import sys
import traceback

import pytest

from . import Framework
from .Framework import readLine

from github.PaginatedList import PaginatedList


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
        for _, _, functionName, _ in traceback.extract_stack():
            if (
                functionName.startswith("test")
                # or functionName == "setUp"
                # or functionName == "tearDown"
            ):
                if (
                    functionName != "test"
                ):  # because in class Hook(Framework.TestCase), method testTest calls Hook.test
                    fileName = os.path.join(
                        os.path.dirname(__file__),
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

        self.__eventFileName = ""
        self.__eventFile = None

        self.actionDataFolder = "PRActionData"
        if not os.path.exists(self.actionDataFolder):
            os.mkdir(self.actionDataFolder)

        repo_config_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "repos", "iarspider_cmssw", "cmssw")
        )
        assert os.path.exists(repo_config_dir)
        assert os.path.exists(os.path.join(repo_config_dir, "repo_config.py"))
        sys.path.insert(0, repo_config_dir)

        if "repo_config" in sys.modules:
            importlib.reload(sys.modules["repo_config"])
            importlib.reload(sys.modules["milestones"])
            importlib.reload(sys.modules["releases"])
            importlib.reload(sys.modules["categories"])
        else:
            importlib.import_module("repo_config")

        self.repo_config = sys.modules["repo_config"]
        assert "iarspider_cmssw" in self.repo_config.__file__

        self.process_pr = importlib.import_module("process_pr").process_pr

    def runTest(self, prId=17):
        repo = self.g.get_repo("iarspider-cmssw/cmssw")
        issue = repo.get_issue(prId)

        if self.recordMode:
            self.__openEventFile("w")
            self.replayData = None
        else:
            f = self.__openEventFile("r")
            self.replayData = json.load(f)

        self.processPrData = self.process_pr(
            self.repo_config,
            self.g,
            repo,
            issue,
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

    def mark_tests(
        self,
        dryRun,
        arch="el8_amd64_gcc12",
        queue="_X",
        required=True,
        unittest=True,
        addon=True,
        relvals=True,
        input_=True,
        comparision=True,
    ):
        repo = self.g.get_repo("iarspider-cmssw/cmssw")
        pr = repo.get_pull(prId)
        commit = pr.get_commits().reversed[0]
        prefix = "cms/" + str(prId) + "/"
        if queue.endswith("_X"):
            queue = queue.rstrip("_X")
        prefix += (queue + "/" if queue else "") + arch
        if not dryRun:
            commit.create_status(
                "success" if all((unittest, addon, relvals, input_, comparision)) else "error",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}".format(prefix, "required" if required else "optional"),
            )
            commit.create_status(
                "success",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}/{1}".format(prefix, "required" if required else "optional"),
                description="Finished",
            )
            commit.create_status(
                "success" if unittest else "error",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}/unittest".format(prefix),
            )
            commit.create_status(
                "success" if addon else "error",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-addon/22833/",
                context="{0}/addon".format(prefix),
            )
            commit.create_status(
                "success" if relvals else "error",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-relvals/43002/",
                context="{0}/relvals".format(prefix),
            )
            commit.create_status(
                "success" if input_ else "error",
                "https://cmssdt.cern.ch/jenkins/job/ib-run-pr-relvals/43000/",
                context="{0}/relvals/input".format(prefix),
            )
            commit.create_status(
                "success" if comparision else "error",
                "https://cmssdt.cern.ch/jenkins/job/compare-root-files-short-matrix/62168/",
                context="{0}/comparision".format(prefix),
            )

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

    def test_revert(self):
        self.runTest()

    def test_start_tests(self):
        self.runTest()

    # # Dummy test
    # def test_mark_rejected(self):
    #     self.mark_tests(False, unittest=False)
    #
    # def test_mark_passed(self):
    #     self.mark_tests(False)

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

    def test_many_commits_warn(self):
        self.runTest(18)

    def test_many_commits_ok(self):
        self.runTest(18)

    def test_too_many_commits(self):
        self.runTest(18)

    # Not yet implemented
    # def test_future_commit(self):
    #     self.runTest()

    # Not yet implemented
    # def test_backdated_commit(self):
    #     self.runTest()
