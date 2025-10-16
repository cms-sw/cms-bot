import copy
import datetime
import functools
import importlib
import json
import os
import os.path
import sys
import traceback
from unittest.mock import patch, PropertyMock

import pytest
import github
import github.GithubObject

from . import Framework
from .Framework import readLine

actions = []
skip_watchers = False


class SkipWatchers:
    def __enter__(self):
        global skip_watchers
        skip_watchers = True

    def __exit__(self, exc_type, exc_val, exc_tb):
        global skip_watchers
        skip_watchers = False


# Utility function for recording calls and optionally calling the original function
def hook_and_call_original(hook, original_function, call_original, self, *args, **kwargs):
    if call_original:
        res = original_function(self, *args, **kwargs)
    else:
        res = None

    res = hook(self, *args, **kwargs, res=res)

    return res


def on_issuecomment_edit(self, *args, **kwargs):
    kwargs.pop("res")

    good_signature = False
    body = ""

    if len(args) == 1 and len(kwargs) == 0:
        body = args[0]
        good_signature = True
    else:
        if len(args) == 0 and set(kwargs.keys()) == {"body"}:
            good_signature = True
            body = kwargs["body"]

    if not good_signature:
        assert False, "IssueComment.edit signature has changed"

    actions.append({"type": "edit-comment", "data": body})
    print("DRY RUN: Updating existing comment with text")
    print(body.encode("ascii", "ignore").decode())


def on_issuecomment_delete(self, *args, **kwargs):
    kwargs.pop("res")
    assert len(kwargs) == 0, "IssueComment.delete signature has changed"
    assert len(args) == 0, "IssueComment.delete signature has changed"
    actions.append({"type": "delete-comment", "data": None})


def on_issue_create_comment(self, *args, **kwargs):
    kwargs.pop("res")
    assert len(kwargs) == 0, "Issue.create_comment signature has changed"
    assert len(args) == 1, "Issue.create_comment signature has changed"

    body = args[0]
    actions.append({"type": "create-comment", "data": body})
    print("DRY RUN: Creating comment with text")
    print(body.encode("ascii", "ignore").decode())


def on_issue_edit(self, *args, **kwargs):
    if kwargs.get("state") == "closed":
        actions.append({"type": "close", "data": None})

    if kwargs.get("state") == "open":
        actions.append({"type": "open", "data": None})

    if kwargs.get("milestone", github.GithubObject.NotSet) != github.GithubObject.NotSet:
        milestone = kwargs["milestone"]
        actions.append(
            {
                "type": "update-milestone",
                "data": {"id": milestone.number, "title": milestone.title},
            }
        )


def on_pr_edit(self, *args, **kwargs):
    actions.append({"type": "edit-pr", "data": kwargs})


def on_pr_merge(self, *args, **kwargs):
    actions.append({"type": "merge-pr", "data": None})


def on_commit_create_status(self, *args, **kwargs):
    assert len(args) == 1, "Commit.Commit.create_status signature has changed"

    state = args[0]
    target_url = kwargs.get("target_url")
    description = kwargs.get("description")
    context = kwargs.get("context")

    actions.append(
        {
            "type": "status",
            "data": {
                "commit": self.sha,
                "state": state,
                "target_url": target_url,
                "description": description,
                "context": context,
            },
        }
    )

    print(
        "DRY RUN: set commit status state={0}, target_url={1}, description={2}, context={3}".format(
            state, target_url, description, context
        )
    )


# TODO: remove once we update pygithub
def get_commit_files(commit):
    # noinspection PyProtectedMember
    return github.PaginatedList.PaginatedList(
        github.File.File,
        commit._requester,
        commit.url,
        {},
        None,
        "files",
    )


# TODO: remove once we update pygithub
def get_commit_files_pygithub(*args, **kwargs):
    kwargs.pop("res")
    assert len(args) == 2, "Signature of process_pr.get_commit_files changed"
    assert len(kwargs) == 0, "Signature of process_pr.get_commit_files changed"
    commit = args[1]
    return (x.filename for x in get_commit_files(commit))


# TODO: remove once we update pygithub
def github__issue__reactions(self):
    """
    :type: dict
    """
    self._completeIfNotSet(self._reactions)
    return self._reactions.value


# TODO: remove once we update pygithub
def github__issuecomment__reactions(self):
    """
    :type: dict
    """
    self._completeIfNotSet(self._reactions)
    return self._reactions.value


# TODO: remove once we update pygithub
def github__issue___initAttributes(self, *args, **kwargs):
    res = kwargs.pop("res")
    self._reactions = github.GithubObject.NotSet

    return res


# TODO: remove once we update pygithub
def github__issuecomment___initAttributes(self, *args, **kwargs):
    res = kwargs.pop("res")
    self._reactions = github.GithubObject.NotSet

    return res


# TODO: remove once we update pygithub
def github__issue___useAttributes(self, *args, **kwargs):
    res = kwargs.pop("res")
    attributes = args[0]

    if "reactions" in attributes:
        self._reactions = self._makeDictAttribute(attributes["reactions"])

    return res


# TODO: remove once we update pygithub
def github__issuecomment___useAttributes(self, *args, **kwargs):
    res = kwargs.pop("res")
    attributes = args[0]

    if "reactions" in attributes:
        self._reactions = self._makeDictAttribute(attributes["reactions"])

    return res


def on_read_bot_cache(*args, **kwargs):
    assert "res" in kwargs
    res = kwargs.pop("res")
    assert len(args) == 1, "Signature of process_pr.read_bot_cache changed"
    assert len(kwargs) == 0, "Signature of process_pr.read_bot_cache changed"
    actions.append({"type": "load-bot-cache", "data": copy.deepcopy(res)})
    return res


def on_write_bot_cache(*args, **kwargs):
    assert "res" in kwargs
    res = kwargs.pop("res")
    assert len(args) == 4, "Signature of process_pr.write_bot_cache changed"
    assert len(kwargs) == 0, "Signature of process_pr.write_bot_cache changed"
    actions.append({"type": "save-bot-cache", "data": args[0]})
    return res


def on_create_property_file(*args, **kwargs):
    kwargs.pop("res")
    assert len(args) == 3, "Signature of process_pr.create_property_file changed"
    assert len(kwargs) == 0, "Signature of process_pr.create_property_file changed"

    out_file_name = args[0]
    parameters = args[1]

    actions.append(
        {"type": "create-property-file", "data": {"filename": out_file_name, "data": parameters}}
    )


def on_set_comment_emoji_cache(*args, **kwargs):
    kwargs.pop("res")
    assert len(args) in range(4, 7)
    assert len(kwargs) <= 2
    comment = args[2]

    actions.append(
        {
            "type": "emoji",
            "data": (comment.id, kwargs.get("emoji", "+1"), kwargs.get("reset_other", True)),
        }
    )


def on_labels_changed(*args, **kwargs):
    kwargs.pop("res")
    assert len(args) == 2
    assert len(kwargs) == 0

    added_labels = args[0]
    removed_labels = args[1]

    actions.append({"type": "add-label", "data": sorted(list(added_labels))})
    actions.append({"type": "remove-label", "data": sorted(list(removed_labels))})


def dummy_fetch_pr_result(*args, **kwargs):
    assert len(args) == 1, "Signature of process_pr.fetch_pr_result changed"
    assert len(kwargs) == 0, "Signature of process_pr.fetch_pr_result changed"

    return "", "ook"


def on_github_init(original_function, self, *args, **kwargs):
    kwargs["per_page"] = 100
    original_function(self, *args, **kwargs)


def hook_read_repo_file(repo_config, repo_file, *args, **kwargs):
    res = kwargs.pop("res")
    if "watchers" in repo_file and skip_watchers:
        return {}

    return res


def hook_fetch_diff(diff_url, *args, **kwargs):

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
                    kwargs["replayDataFolder"],
                    f"{functionName}.json",
                )
    if not fileName:
        raise RuntimeError("Could not determine event file name!")

    res = kwargs.pop("res")
    record = kwargs.pop("record")

    if record:
        with open(fileName, "w") as f:
            json.dump(res, f)
    else:
        with open(fileName) as f:
            res = json.load(f)

    return res


class TestProcessPr(Framework.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_pr_module = None
        self.prId = -1

        global skip_watchers
        skip_watchers = False

    def setUpReactions(self):
        patcher_1 = patch(
            "github.IssueComment.IssueComment.reactions",
            new=property(github__issuecomment__reactions),
            create=True,
        )
        self.patchers.append(patcher_1)
        patcher_1.start()

        patcher_2 = patch(
            "github.Issue.Issue.reactions", new=property(github__issue__reactions), create=True
        )
        self.patchers.append(patcher_2)
        patcher_2.start()

    def setUpHooks(self):
        self.patchers = []
        self.calls = {}
        self.original_functions = {}

        functions_to_patch = [
            {
                "module_path": "github.IssueComment",
                "class_name": "IssueComment",
                "function_name": "edit",
                "hook_function": on_issuecomment_edit,
                "call_original": False,
            },
            {
                "module_path": "github.IssueComment",
                "class_name": "IssueComment",
                "function_name": "delete",
                "hook_function": on_issuecomment_delete,
                "call_original": False,
            },
            {
                "module_path": "github.Issue",
                "class_name": "Issue",
                "function_name": "create_comment",
                "hook_function": on_issue_create_comment,
                "call_original": False,
            },
            {
                "module_path": "github.Issue",
                "class_name": "Issue",
                "function_name": "edit",
                "hook_function": on_issue_edit,
                "call_original": False,
            },
            {
                "module_path": "github.PullRequest",
                "class_name": "PullRequest",
                "function_name": "edit",
                "hook_function": on_pr_edit,
                "call_original": False,
            },
            {
                "module_path": "github.PullRequest",
                "class_name": "PullRequest",
                "function_name": "merge",
                "hook_function": on_pr_merge,
                "call_original": False,
            },
            {
                "module_path": "github.Commit",
                "class_name": "Commit",
                "function_name": "create_status",
                "hook_function": on_commit_create_status,
                "call_original": False,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "get_commit_files",
                "hook_function": get_commit_files_pygithub,
                "call_original": False,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "create_property_file",
                "hook_function": on_create_property_file,
                "call_original": False,
            },
            # Make this function no-op
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "set_emoji",
                "hook_function": lambda *args, **kwargs: None,
                "call_original": False,
            },
            # on_read_bot_cache
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "read_bot_cache",
                "hook_function": on_read_bot_cache,
                "call_original": True,
            },
            # on_write_bot_cache
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "write_bot_cache",
                "hook_function": on_write_bot_cache,
                "call_original": True,
            },
            # Actual handling of emoji cache
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "set_comment_emoji_cache",
                "hook_function": on_set_comment_emoji_cache,
                "call_original": True,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "on_labels_changed",
                "hook_function": on_labels_changed,
                "call_original": False,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "fetch_pr_result",
                "hook_function": dummy_fetch_pr_result,
                "call_original": False,
            },
            # TODO: remove once we update PyGithub
            {
                "module_path": "github.IssueComment",
                "class_name": "IssueComment",
                "function_name": "_initAttributes",
                "hook_function": github__issuecomment___initAttributes,
                "call_original": True,
            },
            # TODO: remove once we update PyGithub
            {
                "module_path": "github.Issue",
                "class_name": "Issue",
                "function_name": "_initAttributes",
                "hook_function": github__issue___initAttributes,
                "call_original": True,
            },
            # TODO: remove once we update PyGithub
            {
                "module_path": "github.IssueComment",
                "class_name": "IssueComment",
                "function_name": "_useAttributes",
                "hook_function": github__issuecomment___useAttributes,
                "call_original": True,
            },
            # TODO: remove once we update PyGithub
            {
                "module_path": "github.Issue",
                "class_name": "Issue",
                "function_name": "_useAttributes",
                "hook_function": github__issue___useAttributes,
                "call_original": True,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "read_repo_file",
                "hook_function": hook_read_repo_file,
                "call_original": True,
            },
            {
                "module_path": "process_pr",
                "class_name": None,
                "function_name": "fetch_diff",
                "hook_function": functools.partial(
                    hook_fetch_diff, record=self.recordMode, replayDataFolder=self.replayDataFolder
                ),
                "call_original": self.recordMode,
            },
        ]

        for func in functions_to_patch:
            module = __import__(func["module_path"], fromlist=func["class_name"])
            if func["class_name"] is not None:
                original_class = getattr(module, func["class_name"])
                original_function = getattr(original_class, func["function_name"])
                fn_to_patch = "{}.{}.{}".format(
                    func["module_path"], func["class_name"], func["function_name"]
                )
            else:
                original_function = getattr(module, func["function_name"])
                fn_to_patch = "{}.{}".format(func["module_path"], func["function_name"])

            side_effect = functools.partial(
                hook_and_call_original,
                func["hook_function"],
                original_function,
                func["call_original"],
            )

            self.original_functions[fn_to_patch] = original_function

            patcher = patch(fn_to_patch, side_effect=side_effect, autospec=True)
            self.patchers.append(patcher)

            # Apply the patch
            patcher.start()

    def tearDown(self):
        for patcher in self.patchers:
            patcher.stop()

        self.process_pr = None
        self.process_pr_module = None

    @staticmethod
    def compareActions(res_, expected_, skip_missing_write_cache):
        def normalize_data(data):
            if isinstance(data, dict):
                return frozenset((key, normalize_data(value)) for key, value in data.items())
            elif isinstance(data, list):
                if data and all(isinstance(x, str) for x in data):
                    return tuple(sorted(str(x) for x in data))
                return tuple(normalize_data(item) for item in data)
            else:
                # Notice: can't compare b64 encoded zlib compressed data
                # directly, rely on load_cache and write_cache actions
                # Reason: different versions of zlib can create different bytestrings
                # due to different heuristics
                if (
                    isinstance(data, str)
                    and data.startswith("cms-bot internal usage<!-- bot cache:")
                    and not data.startswith("cms-bot internal usage<!-- bot cache: {")
                ):
                    data = "cms-bot internal usage<!-- bot cache: blob-->"
                return data

        def normalize_action(action):
            return (action["type"], normalize_data(action["data"]))

        def denormalize_data(data):
            if isinstance(data, frozenset):
                return {key: denormalize_data(value) for key, value in data}
            elif isinstance(data, tuple):
                return [denormalize_data(item) for item in data]
            else:
                return data

        def denormalize_action(normalized_action):
            return {"type": normalized_action[0], "data": denormalize_data(normalized_action[1])}

        res = set([normalize_action(action) for action in res_])
        expected = set([normalize_action(action) for action in expected_])

        if skip_missing_write_cache:
            write_cache_action = normalize_action(
                {"type": "edit-comment", "data": "cms-bot internal usage<!-- bot cache: blob-->"}
            )
            if (write_cache_action in res) and not (write_cache_action in expected):
                expected.add(write_cache_action)

        if res.symmetric_difference(expected):
            for itm in res - expected:
                print("New     action", denormalize_action(itm))

            for itm in expected - res:
                print("Missing action", denormalize_action(itm))

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
                not self.recordActionMode
            ):  # pragma no branch (Branch useful only when recording new tests, not used during automated tests)
                self.assertEqual(readLine(self.__eventFile), "")
            self.__eventFile.close()

    @classmethod
    def setUpClass(cls):
        cls.actionDataFolder = "PRActionData"
        if not os.path.exists(cls.actionDataFolder):
            os.mkdir(cls.actionDataFolder)

        repo_config_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "repos", "iarspider_cmssw", "cmssw")
        )
        assert os.path.exists(repo_config_dir)
        assert os.path.exists(os.path.join(repo_config_dir, "repo_config.py"))
        sys.path.insert(0, repo_config_dir)

        if "repo_config" in sys.modules:
            print("Reloading repo_config...")
            importlib.reload(sys.modules["repo_config"])
            importlib.reload(sys.modules["milestones"])
            importlib.reload(sys.modules["releases"])
            importlib.reload(sys.modules["categories"])
        else:
            importlib.import_module("repo_config")

        cls.repo_config = sys.modules["repo_config"]
        assert "iarspider_cmssw" in cls.repo_config.__file__

    def setUp(self):
        super().setUp()
        self.setUpHooks()
        self.setUpReactions()

        self.__eventFileName = ""
        self.__eventFile = None

        if "process_pr" not in sys.modules:
            importlib.import_module("process_pr")

        self.process_pr_module = sys.modules["process_pr"]
        self.process_pr = self.process_pr_module.process_pr

        global actions
        actions = []

    def runTest(
        self, repo="cmssw", pr_id=17, enable_trace_log=True, skip_missing_write_cache=False
    ):
        repo = self.g.get_repo(f"iarspider-cmssw/{repo}")
        issue = repo.get_issue(pr_id)

        if self.recordActionMode:
            self.__openEventFile("w")
            self.replayData = None
        else:
            f = self.__openEventFile("r")
            self.replayData = json.load(f)

        self.process_pr(
            self.repo_config,
            self.g,
            repo,
            issue,
            dryRun=False,
            cmsbuild_user=self.repo_config.CMSBUILD_USER,
            force=False,
            enableTraceLog=enable_trace_log,
        )
        self.processPrData = actions
        self.checkOrSaveTest(skip_missing_write_cache)
        self.__closeEventReplayFileIfNeeded()

    def checkOrSaveTest(self, skip_missing_write_cache=False):
        if self.recordActionMode:
            json.dump(self.processPrData, self.__eventFile, indent=4)
        else:
            TestProcessPr.compareActions(
                self.processPrData, self.replayData, skip_missing_write_cache
            )

    def mark_tests(
        self,
        *,
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
        pr = repo.get_pull(self.prId)
        commit = pr.get_commits().reversed[0]
        prefix = "cms/" + str(self.prId) + "/"
        if queue.endswith("_X"):
            queue = queue.rstrip("_X")
        prefix += (queue + "/" if queue else "") + arch
        if not dryRun:
            commit.create_status(
                "success" if all((unittest, addon, relvals, input_, comparision)) else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}".format(prefix, "required" if required else "optional"),
            )
            commit.create_status(
                "success",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}/{1}".format(prefix, "required" if required else "optional"),
                description="Finished",
            )
            commit.create_status(
                "success" if unittest else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-tests/38669/",
                context="{0}/unittest".format(prefix),
            )
            commit.create_status(
                "success" if addon else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-addon/22833/",
                context="{0}/addon".format(prefix),
            )
            commit.create_status(
                "success" if relvals else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-relvals/43002/",
                context="{0}/relvals".format(prefix),
            )
            commit.create_status(
                "success" if input_ else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/ib-run-pr-relvals/43000/",
                context="{0}/relvals/input".format(prefix),
            )
            commit.create_status(
                "success" if comparision else "error",
                target_url="https://cmssdt.cern.ch/jenkins/job/compare-root-files-short-matrix/62168/",
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
    #     self.mark_tests(dryRun=False, unittest=False)
    #
    # def test_mark_passed(self):
    #     self.prId = 36
    #     self.mark_tests(dryRun=False)

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

    def test_partial_reset_dirty_squash(self):
        self.runTest(pr_id=23)

    def test_sign_reject(self):
        self.runTest()

    def test_many_commits_warn(self):
        self.runTest(pr_id=18)

    def test_many_commits_ok(self):
        self.runTest(pr_id=18)

    def test_too_many_commits(self):
        self.runTest(pr_id=18)

    def test_draft_pr_opened(self):
        self.runTest(pr_id=21)

    def test_draft_pr_assign(self):
        self.runTest(pr_id=21)

    def test_draft_pr_updated(self):
        self.runTest(pr_id=21)

    def test_draft_pr_start_test(self):
        self.runTest(pr_id=21)

    def test_draft_pr_ready(self):
        self.runTest(pr_id=21)

    def test_draft_pr_ask_ready(self):
        self.runTest(pr_id=21)

    def test_draft_pr_fully_signed(self):
        self.runTest(pr_id=21)

    def test_test_workflow(self):
        self.runTest(pr_id=24)

    def test_test_using_addpkg(self):
        self.runTest(pr_id=24)

    def test_test_using_full(self):
        self.runTest(pr_id=24)

    def test_test_with_pr(self):
        self.runTest(pr_id=24)

    def test_test_for_queue(self):
        self.runTest(pr_id=24)

    def test_test_for_arch(self):
        self.runTest(pr_id=24)

    def test_test_for_quearch(self):
        self.runTest(pr_id=24)

    def test_test_all_params(self):
        self.runTest(pr_id=24)

    def test_testparams_all_params(self):
        self.runTest(pr_id=24)

    def test_backport(self):
        self.runTest(pr_id=26)

    def test_backport_already_seen(self):
        self.runTest(pr_id=26)

    def test_new_issue(self):
        self.runTest(pr_id=27)

    def test_assign_from(self):
        self.runTest(pr_id=27)

    def test_assign_from_invalid(self):
        self.runTest(pr_id=27)

    def test_assign_from_with_label(self):
        self.runTest(pr_id=27)

    def test_convert_cache(self):
        self.runTest(pr_id=25)

    def test_cache_add_missing_items(self):
        self.runTest(pr_id=25)

    def test_ignore_rejected_invalid(self):
        self.runTest(pr_id=25)

    def test_ignore_rejected_valid(self):
        self.runTest(pr_id=25)

    def test_type_invalid(self):
        self.runTest(pr_id=25)

    def test_type_valid(self):
        self.runTest(pr_id=25)

    def test_remove_type(self):
        self.runTest(pr_id=25)

    def test_invalid_test_params(self):
        self.runTest(pr_id=25)

    def test_pr_develop_branch(self):
        self.runTest(pr_id=28)

    def test_future_commit(self):
        self.runTest(pr_id=29)

    def test_create_repo(self):
        self.runTest(pr_id=30)

    def test_ignore_smth(self):
        self.runTest(pr_id=25)

    def test_grant(self):
        self.runTest(pr_id=25)

    def test_code_checks_with(self):
        self.runTest(pr_id=25)

    def test_check_release_format(self):
        func = self.process_pr_module.check_release_format
        params = {}
        ret = func("CMSSW_15_1_X", "", params)
        assert ret[0] == "CMSSW_15_1_X"
        assert params == {"ARCHITECTURE_FILTER": ""}

        params = {}
        ret = func("el8_amd64_gcc12", "", params)
        assert ret[0] == ""
        assert params == {"ARCHITECTURE_FILTER": "el8_amd64_gcc12"}

        params = {}
        ret = func("CMSSW_15_1_X/el8_amd64_gcc12", "", params)
        assert ret[0] == "CMSSW_15_1_X"
        assert params == {"ARCHITECTURE_FILTER": "el8_amd64_gcc12"}

    def test_create_compressed_cache(self):
        with SkipWatchers():
            self.runTest(pr_id=37, enable_trace_log=False)

    def test_read_compressed_cache(self):
        with SkipWatchers():
            self.runTest(pr_id=37, enable_trace_log=False, skip_missing_write_cache=True)

    def test_create_split_cache(self):
        with SkipWatchers():
            self.runTest(pr_id=37, enable_trace_log=False)

    def test_read_split_cache(self):
        with SkipWatchers():
            self.runTest(pr_id=31, enable_trace_log=False, skip_missing_write_cache=True)

    def test_get_backported_pr(self):
        self.runTest(pr_id=25)

    def test_empty_pr(self):
        self.runTest(pr_id=33)

    def test_new_cmsdist_pr(self):
        self.runTest(repo="cmsdist", pr_id=1)

    def test_cmsdist_start_tests(self):
        self.runTest(repo="cmsdist", pr_id=1)

    def test_warn_many_files(self):
        with SkipWatchers():
            self.runTest(pr_id=38, enable_trace_log=False)

    def test_ack_many_files(self):
        with SkipWatchers():
            self.runTest(pr_id=38, enable_trace_log=False)

    def test_too_many_files(self):
        with SkipWatchers():
            self.runTest(pr_id=38, enable_trace_log=False)

    def test_merge_pr(self):
        self.runTest(pr_id=36)

    def test_urgent(self):
        self.runTest(pr_id=9)

    def test_enable_none(self):
        self.runTest(pr_id=9)

    def test_ignore_sign(self):
        self.runTest(pr_id=9)

    def test_orp_issue(self):
        self.runTest(pr_id=39)

    def test_backport_ok(self):
        self.runTest(pr_id=9)

    def test_build_only(self):
        self.runTest(pr_id=40)

    # Test assigning a legacy category -> should not be assigned
    def test_assign_legacy_cat(self):
        import datetime

        old_repo_config = copy.deepcopy(self.repo_config.LEGACY_CATEGORIES)
        # Before the https://github.com/iarspider-cmssw/cmssw/pull/43
        self.repo_config.LEGACY_CATEGORIES["cmssw"]["upgrade"] = datetime.datetime(
            year=2025, month=7, day=29, hour=16, minute=6, tzinfo=datetime.timezone.utc
        ) - datetime.timedelta(days=1)
        self.runTest(pr_id=43)
        self.repo_config.LEGACY_CATEGORIES = old_repo_config

    # Test assigning a legacy category in a PR opened before category became legacy -> should be assigned
    def test_preserve_legacy_cat(self):
        import datetime

        old_repo_config = copy.deepcopy(self.repo_config.LEGACY_CATEGORIES)
        # After the https://github.com/iarspider-cmssw/cmssw/pull/43
        self.repo_config.LEGACY_CATEGORIES["cmssw"]["upgrade"] = datetime.datetime(
            year=2025, month=7, day=29, hour=16, minute=6, tzinfo=datetime.timezone.utc
        ) + datetime.timedelta(days=1)
        self.runTest(pr_id=43)
        self.repo_config.LEGACY_CATEGORIES = old_repo_config

    def test_autoassign_legacy_cat(self):
        import datetime

        old_repo_config = copy.deepcopy(self.repo_config.LEGACY_CATEGORIES)
        # Before the https://github.com/iarspider-cmssw/cmssw/pull/44
        self.repo_config.LEGACY_CATEGORIES["cmssw"]["upgrade"] = datetime.datetime(
            year=2025, month=10, day=2, hour=9, minute=7, tzinfo=datetime.timezone.utc
        ) - datetime.timedelta(days=1)
        self.runTest(pr_id=44)
        self.repo_config.LEGACY_CATEGORIES = old_repo_config
