#!/usr/bin/env python3
import argparse
import datetime
import io
import os
import shutil
import sys
import urllib
import urllib.error

try:
    import github
except ImportError:
    print("WARNING: module github not available, will not check issue/PR status")
    github = None

import libib

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo

if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 6):
    print("This script requires Python 3.6 or newer!", file=sys.stderr)
    exit(0)

g = None
repo_cache = {}
issue_cache = {}


def is_maybe_resolved(ib_date, issue):
    global repo_cache

    y, m, d, h = [int(x) for x in ib_date.split("-", 5)[:-1] if x]
    h = h // 100

    ib_datetime = datetime.datetime(
        y, m, d, h, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )

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
        closed_at = issue.closed_at.replace(tzinfo=datetime.timezone.utc).astimezone(
            datetime.timezone(datetime.timedelta(hours=2))
        )
    else:
        closed_at = datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=2)))

    return issue.state == "closed" and closed_at < ib_datetime


known_failures = {
    "build": [
        {
            "module": "RecoTracker/PixelSeeding",
            "type": "compWarning",
            "issue": 45340,
        },
        {
            "module": "Validation/CTPPS",
            "type": "compError",
            "issue": 45304,
        },
    ],
    "utest": [
        {"module": "FWCore/Concurrency/testFWCoreConcurrencyCatch2", "issue": 45402},
    ],
    "relval": [
        {
            "workflow": "280.0",
            "step": 1,
            "exit_code": "SIGSEGV",
            "func": "amptset_",
            "issue": 33682,
        },
        {"workflow": "29696.0", "step": 1, "exit_code": "DAS_ERROR", "issue": 45371},
        {"workflow": "29700.0", "step": 1, "exit_code": "DAS_ERROR", "issue": 45371},
        {"workflow": "181.1", "step": 2, "exit_code": "OtherCMS", "issue": 44866},
        {
            "workflow": "29634.501",
            "step": 3,
            "exit_code": "SIGABRT",
            "issue": 45177,
            "assertion": "Assertion `commonParamsGPU_.thePitchY == p.thePitchY` failed",
        },
        {
            "workflow": "29634.502",
            "step": 3,
            "exit_code": "SIGABRT",
            "issue": 45177,
            "assertion": "Assertion `commonParamsGPU_.thePitchY == p.thePitchY` failed",
        },
        {
            "workflow": "546.0",
            "step": 2,
            "exit_code": "ProductNotFound",
            "issue": 45411,
        },
        {
            "workflow": "547.0",
            "step": 3,
            "exit_code": "ProductNotFound",
            "issue": 45411,
        },
        {
            "workflow": "548.0",
            "step": 3,
            "exit_code": "ProductNotFound",
            "issue": 45411,
        },
        {
            "workflow": "1001.3",
            "step": 2,
            "exit_code": "ProductNotFound",
            "issue": 45385,
        },
        {
            "workflow": "1001.4",
            "step": 2,
            "exit_code": "ProductNotFound",
            "issue": 45385,
        },
        {
            "workflow": "1002.3",
            "step": 2,
            "exit_code": "ProductNotFound",
            "issue": 45385,
        },
        {
            "workflow": "1002.4",
            "step": 2,
            "exit_code": "ProductNotFound",
            "issue": 45385,
        },
    ],
}


def get_known_failure(failure_type, **kwargs):
    for failure in known_failures.get(failure_type, []):
        if failure_type == "relval" and failure["exit_code"] != kwargs["exit_code"]:
            continue
        if all(k == "details" or k == "line" or failure[k] == kwargs[k] for k in kwargs):
            return failure
    else:
        return None


def main():
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
                    buffer = io.StringIO()
                    print(f"### {arch}\n", file=f)
                    if any(
                        (
                            errors[arch]["build"],
                            errors[arch]["utest"],
                            errors[arch]["relval"],
                        )
                    ):
                        all_known = True
                        print("| What failed | Description | Issue |", file=buffer)
                        print("| ----------- | ----------- | ----- |", file=buffer)
                        for error in errors[arch]["build"]:
                            extra_data = "TBD"
                            known_failure = get_known_failure(
                                "build", module=error.name, type=error.data[0]
                            )
                            if known_failure:
                                if is_maybe_resolved(ib_date, known_failure["issue"]):
                                    extra_data = ":exclamation_mark: " + str(
                                        known_failure["issue"]
                                    )
                                    all_known = False
                                else:
                                    continue
                            else:
                                all_known = False
                            print(
                                f"| [{error.name}]({error.url}) | {error.data[1]}x "
                                f"{error.data[0]} | {extra_data} |",
                                file=buffer,
                            )

                        for error in errors[arch]["utest"]:
                            extra_data = "TBD"
                            known_failure = get_known_failure("utest", module=error.name)
                            if known_failure:
                                if is_maybe_resolved(ib_date, known_failure["issue"]):
                                    extra_data = ":exclamation_mark: " + str(
                                        known_failure["issue"]
                                    )
                                    all_known = False
                                else:
                                    continue
                            else:
                                all_known = False

                            print(
                                f"| [{error.name}]({error.url}) | TBD | {extra_data} |",
                                file=buffer,
                            )

                        for error in errors[arch]["relval"]:
                            assert isinstance(error, libib.LogEntry)
                            extra_data = "TBD"
                            known_failure = get_known_failure(
                                "relval",
                                **error.data,
                            )
                            if known_failure:
                                if is_maybe_resolved(ib_date, known_failure["issue"]):
                                    extra_data = ":exclamation_mark: #" + str(
                                        known_failure["issue"]
                                    )
                                    all_known = False
                                else:
                                    continue
                            else:
                                all_known = False

                            desc = error.data.get("details", None) or error.data["exit_code"]

                            print(
                                f"| [{error.name}]({error.url}) | {desc} | {extra_data} |",
                                file=buffer,
                            )

                        if all_known:
                            print('<span style="color:orange">Only known issues</span>', file=f)
                        else:
                            buffer.seek(0)
                            shutil.copyfileobj(buffer, f)
                            buffer.close()
                        print("", file=f)
                    else:
                        print('<span style="color:green">No issues</span>', file=f)


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
    main()
    # print(libib.get_expected_ibs("CMSSW_14_1_X", "2024-07-03-2300"))
