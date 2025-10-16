import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import process_pr


def v_regexes():
    with open(os.path.dirname(__file__) + "/data/cmsbuild_test_cases.json") as f:
        test_data = json.load(f)

    for case in test_data:
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


if __name__ == "__main__":
    process_pr.setup_logging(logging.ERROR)
    v_regexes()
