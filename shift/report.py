#!/usr/bin/env python3
import argparse
import base64
import copy
import datetime
import io
import json
import os
import shutil
import sys
import time
import urllib
import urllib.error

import es_utils

try:
    import github
except ImportError:
    print("WARNING: module github not available, will not check issue/PR status")
    github = None

import libib

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo

if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 7):
    print("This script requires Python 3.7 or newer!", file=sys.stderr)
    exit(0)

g = None
repo_cache = {}
issue_cache = {}
localtz = None


# Taken from https://stackoverflow.com/a/59673310
def currenttz():
    if time.daylight:
        return datetime.timezone(datetime.timedelta(seconds=-time.altzone), time.tzname[1])
    else:
        return datetime.timezone(datetime.timedelta(seconds=-time.timezone), time.tzname[0])


def search_es(index, **kwargs):
    kwargs.pop("line", None)
    kwargs.pop("details", None)
    query = " AND ".join(
        "{0}:{1}".format(k, f'\\"{v}\\"' if isinstance(v, str) else v) for k, v in kwargs.items()
    )
    # if kwargs.get("workflow", None) == "280.0":
    #     print(f"Sending query: index cmssdt-{index}-failures, query {query}")
    ret = es_utils.es_query(
        f"cmssdt-{index}-failures", query, start_time=0, end_time=1000 * int(time.time())
    )
    # if kwargs.get("workflow", None) == "280.0":
    #     print(ret)
    #     exit(0)
    return tuple(x["_source"] for x in ret["hits"]["hits"])


def is_issue_closed(ib_date, issue):
    global repo_cache

    y, m, d, h = [int(x) for x in ib_date.split("-", 5)[:-1] if x]
    h = h // 100

    ib_datetime = datetime.datetime(y, m, d, h, 0, tzinfo=localtz)

    if g is None:
        return False

    issue = str(issue)

    if "#" in issue:
        repo_name, issue_id = issue.split("#")
    else:
        repo_name = "cms-sw/cmssw"
        issue_id = issue

    if not repo_name:
        repo_name = "cms-sw/cmssw"

    if isinstance(issue_id, str):
        issue_id = int(issue_id)

    repo = repo_cache.get(repo_name, None)
    if not repo:
        repo = g.get_repo(repo_name)
        repo_cache[repo_name] = repo

    issue = issue_cache.get(issue_id)
    if not issue:
        issue = repo.get_issue(issue_id)
        issue_cache[issue_id] = issue

    if issue.closed_at:
        closed_at = issue.closed_at.replace(tzinfo=datetime.timezone.utc).astimezone(localtz)
    else:
        closed_at = datetime.datetime.now(tz=localtz)

    return issue.state == "closed" and (closed_at < ib_datetime)
    # return False


def get_known_failure(failure_type, **kwargs):
    res = search_es(failure_type, **kwargs)
    if res:
        return res[0]
    else:
        return None


def main():
    def format_issue(issue_):
        issue_ = str(issue_)
        if "#" not in issue_:
            repo = "cms-sw/cmssw"
            issue_no = issue_
            issue_txt = f"#{issue_no}"
        else:
            repo, issue_no = issue_.split("#", 1)
            issue_txt = f"{repo}#{issue_no}"

        return f"[{issue_txt}](https://github.com/{repo}/{issue_no})"

    global g
    if github:
        g = github.Github(
            login_or_token=open(os.path.expanduser("~/.github-token")).read().strip()
        )
    else:
        g = None

    # print(f"Loaded {len(exitcodes)} exit code(s)")
    libib.setup_logging()
    libib.get_exitcodes()

    structure = libib.fetch("SDT/html/data/structure.json")

    if args.series == "default":
        series = structure["default_release"]
    else:
        series = args.series

    try:
        libib.fetch("SDT/html/data/" + series + ".json")
    except urllib.error.HTTPError:
        print(f"!ERROR: Invalid release {series}!")
        exit(1)

    if (not args.date) or args.date == "auto":
        ib_dates = libib.get_ib_dates(series)
    else:
        ib_dates = [args.date]

    os.makedirs("out", exist_ok=True)
    for ib_date in ib_dates:
        for flav, comp in libib.get_ib_comparision(ib_date, series).items():
            if comp is None:
                # print(f"No IB found for flavor {flav} and date {ib_date}")
                continue
            release_name, errors = libib.check_ib(comp)
            with open(f"out/{release_name}.md", "w") as f:
                print(f"## {release_name}\n", file=f)
                # print("-- INSERT SCREENSHOT HERE --\n", file=f)
                for arch in errors:
                    print(f"### {arch}\n", file=f)
                    if any(
                        (
                            errors[arch]["build"],
                            errors[arch]["utest"],
                            errors[arch]["relval"],
                        )
                    ):
                        print(
                            "| What failed | Description | GH Issue | Failure descriptor |",
                            file=f,
                        )
                        print(
                            "| ----------- | ----------- | -------- | ------------------ |",
                            file=f,
                        )
                        for error in errors[arch]["build"]:
                            issue_data = "TBD"
                            failure_desc = dict(module=error.name, type=error.data[0])
                            known_failure = get_known_failure("build", **failure_desc)
                            failure_desc["index"] = "build"
                            if known_failure:
                                issue_data = format_issue(known_failure["issue"])
                                if is_issue_closed(ib_date, known_failure["issue"]):
                                    issue_data = ":exclamation_mark: " + issue_data

                            if not known_failure:
                                failure_data = (
                                    base64.b64encode(json.dumps(failure_desc).encode())
                                    .decode()
                                    .replace("\n", "@")
                                )
                            else:
                                failure_data = "known"

                            print(
                                f"| [{error.name}]({error.url}) | {error.data[1]}x "
                                f"{error.data[0]} | {issue_data} | `build`, `{failure_data}` |",
                                file=f,
                            )

                        for error in errors[arch]["utest"]:
                            issue_data = "TBD"
                            known_failure = get_known_failure("utest", module=error.name)
                            if known_failure:
                                issue_data = format_issue(known_failure["issue"])
                                if is_issue_closed(ib_date, known_failure["issue"]):
                                    issue_data = ":exclamation_mark: " + issue_data

                            if not known_failure:
                                failure_desc = dict(module=error.name, index="utest")
                                failure_data = (
                                    base64.b64encode(json.dumps(failure_desc).encode())
                                    .decode()
                                    .replace("\n", "@")
                                )
                            else:
                                failure_data = "known"

                            print(
                                f"| [{error.name}]({error.url}) | TBD | {issue_data} | `utest`, `{failure_data}` |",
                                file=f,
                            )

                        for error in errors[arch]["relval"]:
                            assert isinstance(error, libib.LogEntry)
                            issue_data = "TBD"
                            known_failure = get_known_failure(
                                "relval",
                                **error.data,
                            )
                            if known_failure:
                                issue_data = format_issue(known_failure["issue"])
                                if is_issue_closed(ib_date, known_failure["issue"]):
                                    issue_data = ":exclamation_mark: " + issue_data

                            desc = error.data.get("details", None) or error.data["exit_code_name"]
                            if not known_failure:
                                failure_desc = copy.deepcopy(error.data)
                                failure_desc.pop("line", None)
                                failure_desc.pop("details", None)
                                failure_desc["index"] = "relval"
                                failure_data = (
                                    base64.b64encode(json.dumps(failure_desc).encode())
                                    .decode()
                                    .replace("\n", "@")
                                )
                            else:
                                failure_data = "known"
                            print(
                                f"| [{error.name}]({error.url}) | {desc} | {issue_data} | `relval`, `{failure_data}` |",
                                file=f,
                            )

                        print("", file=f)
                    else:
                        print('<span style="color:green">No issues</span>\n', file=f)


def validate_date(x):
    if x == "auto":
        return x
    if libib.date_rex.match(x.rsplit("_", 1)[1]):
        return x.rsplit("_", 1)[1]
    else:
        raise ValueError()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="CMSSDT Shift Assistant")
    parser.add_argument(
        "-s",
        "--series",
        default="default",
        help="Release series to process or 'default' to use 'default_release' from "
        "structure.json",
    )
    parser.add_argument(
        "-d",
        "--date",
        default="auto",
        type=validate_date,
        help="IB date to process (YYYY-MM-DD) or 'auto' to process two last IBs",
        # nargs="*",
    )
    args = parser.parse_args()
    localtz = currenttz()
    main()
    # print(libib.get_expected_ibs("CMSSW_14_1_X", "2024-07-03-2300"))
