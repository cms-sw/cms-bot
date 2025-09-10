#!/usr/bin/env python3

import datetime
import json
import logging
import os
import sys
import urllib.error
from urllib.error import HTTPError

# noinspection PyUnresolvedReferences
import libib

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo

from github_utils import get_commit

try:
    current_shifter = libib.fetch("/SDT/shifter.txt", content_type=libib.ContentType.TEXT)
    exit_code = 0
except (urllib.error.URLError, urllib.error.HTTPError) as e:
    print("WARNING: failed to get current_shifter!")
    print(e)
    current_shifter = "all"
    exit_code = 1

# cache_root = os.path.join(os.getenv("JENKINS_HOME"), "workspace/cache/cms-ib-notifier")

header = f"@{current_shifter} New IB failures found, please check:"

table_header = """# {rel}-{ib_date} for {arch}
| Error | Additional data |
| --- | --- |"""

max_report_lines = 19


def isoparse(strDate):
    return datetime.datetime.strptime(strDate, "%Y-%m-%dT%H:%M:%SZ")


def main():
    workspace = os.getenv("WORKSPACE", os.getcwd())
    # os.makedirs(cache_root, exist_ok=True)

    libib.setup_logging(logging.DEBUG)
    libib.get_exitcodes()

    ib_dates = libib.get_ib_dates("default")

    commit_dates = {}

    changed_rels = set()
    oldest_parent_sha = ""
    oldest_parent_date = datetime.datetime.now().astimezone()
    for commit_id in sys.argv[1:]:
        print("Processing commit {}".format(commit_id))
        commit_info = get_commit("cms-sw/cms-sw.github.io", commit_id)
        if "sha" not in commit_info:
            print("Invalid or missing commit-id {}".format(commit_id))
            continue
        try:
            commit_author = commit_info["commit"]["author"]
        except KeyError:
            print("Commit {} has no author!".format(commit_id))
            continue
        if commit_author["email"] != "cmsbuild@cern.ch":
            print(
                "Commit {} not from cmsbuild: {} <{}>".format(
                    commit_id, commit_author["name"], commit_author["email"]
                )
            )
            continue

        commit_date = libib.date_fromisoformat(commit_author["date"])
        commit_dates[commit_id] = commit_date

        has_changed_release = False

        for change in commit_info["files"]:
            if not change["filename"].startswith("_data/CMSSW"):
                continue
            relname = change["filename"].replace("_data/", "").replace(".json", "")
            print("Release {} changed".format(relname))
            changed_rels.add(relname)
            has_changed_release = True

        if has_changed_release:
            parent_sha = commit_info["parents"][0]["sha"]
            parent_commit_info = get_commit("cms-sw/cms-sw.github.io", parent_sha)
            parent_date = libib.date_fromisoformat(parent_commit_info["commit"]["author"]["date"])
            if parent_date < oldest_parent_date:
                oldest_parent_sha = parent_sha
                oldest_parent_date = parent_date

    if len(changed_rels) == 0:
        print("No releases changed")
        exit(0)

    newest_commit_date = max(commit_dates.values())
    newest_commit_id = [k for k, v in commit_dates.items() if v == newest_commit_date]
    newest_commit_id = newest_commit_id[0]

    first_report = True
    payload_index = 0

    for ib_date in ib_dates:
        for rel in changed_rels:
            old_result = None
            old_data = None
            try:
                old_data = libib.fetch(
                    f"https://github.com/cms-sw/cms-sw.github.io/raw/{oldest_parent_sha}/data%2F{rel}.json",
                    timeout=60,
                )
            except HTTPError as e:
                if e.code != 404:
                    raise

            if old_data:
                old_comparision = libib.get_ib_results(ib_date, None, old_data)
                if old_comparision:
                    _, old_result = libib.check_ib(old_comparision)

            try:
                new_data = libib.fetch(
                    f"https://github.com/cms-sw/cms-sw.github.io/raw/{newest_commit_id}/data%2F{rel}.json",
                    timeout=60,
                )
            except HTTPError as e:
                if e.code == 404:
                    print(f"Release {rel} not found on github!")
                    continue
                else:
                    raise
            new_comparision = libib.get_ib_results(ib_date, None, new_data)
            if new_comparision is None:
                continue

            _, new_result = libib.check_ib(new_comparision)

            for arch in new_result:
                arch_report = []
                for error in new_result[arch]["build"]:
                    if old_result and arch in old_result and error in old_result[arch]["build"]:
                        continue

                    failure_desc = dict(module=error.name, type=error.data[0])
                    known_failure = libib.get_known_failure("build", **failure_desc)
                    if known_failure:
                        continue

                    arch_report.append(
                        f"| [{error.name}]({error.url}) | {error.data[1]}x {error.data[0]} | "
                    )

                for error in new_result[arch]["utest"]:
                    if old_result and arch in old_result and error in old_result[arch]["utest"]:
                        continue
                    known_failure = libib.get_known_failure("utest", module=error.name)
                    if known_failure:
                        continue

                    arch_report.append(f"| [{error.name}]({error.url}) | TBD | ")

                for error in new_result[arch]["relval"]:
                    if old_result and arch in old_result and error in old_result[arch]["relval"]:
                        continue

                    if error.data["step"] != -1:
                        known_failure = libib.get_known_failure(
                            "relval",
                            **error.data,
                        )
                    else:
                        known_failure = None
                    if known_failure:
                        continue

                    desc = error.data.get("details", None) or error.data["exit_code_name"]

                    arch_report.append(f"| [{error.name}]({error.url}) | {desc} | ")

                if len(arch_report) > (max_report_lines + 1):
                    arch_report_l = len(arch_report)
                    arch_report = arch_report[:max_report_lines]
                    arch_report.append(
                        f"| :warning: {arch_report_l - max_report_lines} error(s) more | Check IB status page | "
                    )

                if arch_report:
                    arch_report.insert(
                        0,
                        table_header.format(rel=rel, ib_date=ib_date.rsplit("-", 1)[0], arch=arch),
                    )
                    if first_report:
                        arch_report.insert(0, header)
                        first_report = False

                    payload = {"text": "\n".join(arch_report)}
                    jsondata = json.dumps(payload).encode("utf-8")
                    with open(f"{workspace}/report_{payload_index:03d}.json", "wb") as f:
                        f.write(jsondata)

                    payload_index += 1

    if payload_index > 0:
        with open(f"{workspace}/submit.sh", "w") as f:
            print("#!/bin/bash", file=f)
            for i in range(payload_index):
                print(
                    f'curl -H "Content-Type: application/json" --data-binary "@report_{i:03d}.json" $MM_WEBHOOK_URL',
                    file=f,
                )
                print(f"rm -f report_{i:03d}.json", file=f)
    else:
        if os.path.exists(f"{workspace}/submit.sh"):
            os.unlink(f"{workspace}/submit.sh")


if __name__ == "__main__":
    main()
    exit(exit_code)
