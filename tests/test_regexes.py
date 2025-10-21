import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import process_pr

import logging

process_pr.logger = logging.getLogger("dummy")


def load_test_data():
    import json
    from pathlib import Path

    path = Path(__file__).parent / "data/cmsbuild_test_cases.json"

    with path.open() as f:
        test_data = json.load(f)

    return test_data


@pytest.mark.parametrize("case", load_test_data(), ids=lambda case: case["id"])
def test_regex(case):
    print("Processing case", case["id"])
    params = {}
    expect = case["expect"]
    first_line = process_pr.preprocess_comment_text(case["s"])[0]
    print("\tTest string:", first_line)
    ret = process_pr.check_test_cmd(first_line, "cms-sw/cmssw", params)
    assert ret[0] == case["should_match"]
    if case["should_match"]:
        assert ret[1] == " ".join(expect.get("cms_prs", []))
        assert ret[2] == ",".join(set(expect.get("workflows", [])))
        assert ret[3] == expect.get("release_queue", "")
        assert ret[4] == (expect["action"] == "build")
