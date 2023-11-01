#!/usr/bin/env python3

import datetime
import json
import logging
import os
import sys
import urllib.error

from github_utils import github_api
from urllib.error import HTTPError

# noinspection PyUnresolvedReferences
import libib

# noinspection PyUnresolvedReferences
from libib import PackageInfo, ErrorInfo

try:
    current_shifter = libib.fetch("/SDT/shifter.txt", content_type=libib.ContentType.TEXT)
    exit_code = 0
except (urllib.error.URLError, urllib.error.HTTPError) as e:
    print("WARNING: failed to get current_shifter!")
    print(e)
    current_shifter = "all"
    exit_code = 1

cache_root = os.path.join(os.getenv("JENKINS_HOME"), "workspace/cache/cms-ib-notifier")

header = f"@{current_shifter} New IB failures found, please check:"

table_header = """# {rel}-{ib_date} for {arch}
| Error | Additional data |
| --- | --- |"""

max_report_lines = 19


def get_commit_info(repo, commit):
    return github_api(
        uri="/repos/{}/commits/{}".format(repo, commit), method="GET", all_pages=False
    )


def isoparse(strDate):
    return datetime.datetime.strptime(strDate, "%Y-%m-%dT%H:%M:%SZ")


def main():
    workspace = os.getenv("WORKSPACE", os.getcwd())
    os.makedirs(cache_root, exist_ok=True)

    libib.setup_logging(logging.DEBUG)
    libib.get_exitcodes()

    ib_dates = libib.get_ib_dates("default")

    commit_dates = {}

    changed_rels = set()
    for commit_id in sys.argv[1:]:
        print("Processing commit {}".format(commit_id))
        commit_info = get_commit_info("cms-sw/cms-sw.github.io", commit_id)
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

        for change in commit_info["files"]:
            if not change["filename"].startswith("_data/CMSSW"):
                continue
            relname = change["filename"].replace("_data/", "").replace(".json", "")
            print("Release {} changed".format(relname))
            changed_rels.add(relname)

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
            old_data_file = os.path.join(cache_root, "{}.json".format(rel))
            old_result = None
            if os.path.exists(old_data_file):
                print(f"Loading cached release {rel}")
                old_data = json.load(open(old_data_file, "r"))
                old_comparision = libib.get_ib_results(ib_date, None, old_data)
                if old_comparision:
                    _, old_result = libib.check_ib(old_comparision)
            else:
                print(f"No cache for release {rel}")

            try:
                new_data = libib.fetch(
                    f"https://github.com/cms-sw/cms-sw.github.io/raw/{newest_commit_id}/data%2F{rel}.json"
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

                    arch_report.append(
                        f"| [{error.name}]({error.url}) | {error.data[1]}x {error.data[0]} | "
                    )

                for error in new_result[arch]["utest"]:
                    if old_result and arch in old_result and error in old_result[arch]["utest"]:
                        continue

                    arch_report.append(f"| [{error.name}]({error.url}) | TBD | ")

                for error in new_result[arch]["relval"]:
                    if old_result and arch in old_result and error in old_result[arch]["relval"]:
                        continue

                    arch_report.append(f"| [{error.name}]({error.url}) | {error.data} | ")

                if len(arch_report) > (max_report_lines + 1):
                    arch_report_l = len(arch_report)
                    arch_report = arch_report[:max_report_lines]
                    arch_report.append(
                        f"| :warning: {arch_report_l-max_report_lines} error(s) more | Check IB status page | "
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

    # Save new json files
    for rel in changed_rels:
        url_ = (
            f"https://github.com/cms-sw/cms-sw.github.io/raw/{newest_commit_id}/_data%2F{rel}.json"
        )
        try:
            data = libib.fetch(url_, libib.ContentType.TEXT)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            else:
                pass
        else:
            with open(os.path.join(cache_root, "{}.json".format(rel)), "w") as f:
                f.write(data)


if __name__ == "__main__":
    main()
    exit(exit_code)
