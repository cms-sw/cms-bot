import json
import logging
import sys
from pathlib import Path

from github import Github
from github.IssueComment import IssueComment

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_dummy_logger(name="dummy"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.CRITICAL + 1)  # Suppress all messages
    logger.propagate = False  # Prevent propagation to root logger
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger


import process_pr

process_pr.logger = get_dummy_logger()
process_pr.addLoggingLevel("TRACE", logging.DEBUG - 5)


def load_comments(json_str):
    data = json.loads(json_str)

    # Create a dummy Github object (not used unless you want to call GitHub)
    g = Github("dummy_token")

    result = []

    for itm in data:
        # Internal hack to create object manually (be careful with _ prefix usage)
        comment = IssueComment(
            requester=g._Github__requester, headers={}, attributes=itm, completed=True
        )

        result.append(comment)

    return result


keys = (
    "protocol",
    "verb",
    "host",
    "unknown1",
    "url",
    "req_headers",
    "unknown2",
    "status",
    "resp_headers",
    "body",
)


def get_comments_from_replaydata(fname):
    http_requests = []
    with open(fname) as f:
        buffer = []
        for line in f:
            line = line.strip()
            if line:
                buffer.append(line)
            else:
                http_requests.append(dict(zip(keys, buffer)))
                buffer = []

    print("Loaded", len(http_requests), "requests")
    comments = []
    for req in http_requests:
        # print("{verb} {host}{url}".format(**req))
        if req["verb"] == "GET" and "/comments" in req["url"]:
            comments.extend(load_comments(req["body"]))

    return comments


def main():
    for fn in Path("ReplayData").glob("*.txt"):
        print("Loading file", fn)
        comments = get_comments_from_replaydata(fn)
        print("Loaded", len(comments), "comment(s)")
        cache = process_pr.extract_bot_cache(comments)
        if not cache:
            print("WARNING: no cache in", str(fn) + "!")
            continue
        jfn = Path("PRActionData") / fn.with_suffix(".json").name
        with jfn.open() as f:
            jdata = json.load(f)

        jcache = None
        for jitem in jdata:
            if jitem["type"] == "load-bot-cache":
                jcache = jitem["data"]
                break

        if not jcache:
            print("ERROR: no load-bot-cache in", str(jfn) + "!")
            continue

        assert jcache == cache


if __name__ == "__main__":
    main()
