import argparse
import io
import json
import os
import pickle
import re
import urllib
import urllib.error
import urllib.request
from enum import Enum
from typing import Any

# ErrorInfo class is used during unpickling
# noinspection PyUnresolvedReferences
from showBuildLogs import PackageInfo, ErrorInfo

date_rex = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}00")
url_root = "https://cmssdt.cern.ch/"
exitcodes = {}


class ContentType(Enum):
    JSON = 1
    TEXT = 2
    BINARY = 3


def make_url(url: str):
    url = url.lstrip("/")
    if url.startswith("http"):
        return url
    else:
        return url_root + url


def fetch(url: str, content_type: ContentType = ContentType.JSON) -> Any:
    url = make_url(url)
    try:
        response = urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        print(f"Request to {url} failed with code {e.code}")
        print(f"{e.read()}")
        raise
    except urllib.error.URLError as e:
        print(f"Request to {url} failed with error {e.reason}")
        raise
    if response.getcode() != 200:
        print(f"Request to {url} failed with code {response.getcode()}")
        raise RuntimeError()

    content = response.read()
    match content_type:
        case ContentType.JSON:
            return json.loads(content)
        case ContentType.TEXT:
            return content.decode("utf-8")
        case ContentType.BINARY:
            return content


def check_ib(data):
    log = {}
    print(f"Found IB {data['release_name']}")
    ib_date = data["ib_date"].rsplit("-", 1)[0]
    queue = data["release_queue"]
    for arch in data["tests_archs"]:
        # print(f"\tFound arch {arch}")
        log[arch] = [
            "| What failed | Description | Issue |",
            "| ----------- | ----------- | ----- |",
        ]

    print("== Compilation results ==")
    for bld in data["builds"]:
        arch = bld["arch"]
        print(f"\tArch: {arch}, status: {bld['passed']}")
        if bld["passed"] != "passed":
            bldFile = bld["file"].replace("/data/sdt", "")
            summIO = io.BytesIO(fetch(bldFile, content_type=ContentType.BINARY))
            pklr = pickle.Unpickler(summIO)
            [rel, plat, _] = pklr.load()
            _ = pklr.load()
            _ = pklr.load()
            _ = pklr.load()
            packageList: list[PackageInfo] = pklr.load()
            summIO.close()

            url_prefix = f"https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/{plat}/{rel}"

            for pkg in [x for x in packageList if x.errInfo]:
                for err, cnt in pkg.errSummary.items():
                    if err == "ignoreWarning":
                        continue

                    log[arch].append(
                        f"| [{pkg.name()}]({url_prefix}/{pkg.name()}) | {cnt}x {err} | TBD |"
                    )

    print("== Unit test results ==")
    for ut in data["utests"]:
        arch = ut["arch"]
        print(f"\tArch: {arch}, status: {ut['passed']}")
        if ut["passed"] == "failed":
            utFile = ut["file"]
            utFile = utFile.replace("/data/sdt", "").replace(
                "unitTests-summary.log", "unitTestResults.pkl"
            )

            utIO = io.BytesIO(fetch(utFile, ContentType.BINARY))
            # utIO.seek(0)
            pklr = pickle.Unpickler(utIO)
            unitTestResults = pklr.load()
            for pkg, utData in unitTestResults.items():
                utList, passed, failed = utData
                if failed > 0:
                    webURL_t = f"https://cmssdt.cern.ch/SDT/cgi-bin/logreader/{arch}/{data['release_name']}/unitTestLogs/{pkg}#/{{lineStart}}-{{lineEnd}}"
                    # print(f"\t\t{failed} Unit Test{'s' if failed>1 else ''} in {pkg}")
                    utlData = fetch(
                        f"SDT/cgi-bin/buildlogs/raw_read_config/{arch}/{data['release_name']}/unitTestLogs/{pkg}",
                        ContentType.JSON,
                    )
                    for ctl in utlData["show_controls"]:
                        if ctl["name"] != "Issues":
                            continue
                        for obj in ctl["list"]:
                            if obj["control_type"] == "Issues" and re.match(
                                r".* failed at line #\d+", obj["name"]
                            ):
                                webURL = webURL_t.format(**obj)
                                # print("\t\t" + obj["name"])
                                utName = pkg + "/" + obj["name"].split(" ", 1)[0]
                                log[arch].append(f"| [{utName}]({webURL}) | ? | ? |")
                                # print("\t\t" + webURL)

    print("== RelVal results ==")
    for rv in data["relvals"]:
        arch = rv["arch"]
        print(f"\tArch: {rv['arch']}, status: {rv['passed']}")
        if not rv["passed"]:
            rvData = fetch(
                f"SDT/public/cms-sw.github.io/data/relvals/{arch}/{ib_date}/{queue}.json",
                ContentType.JSON,
            )
            for rvItem in rvData:
                exitcode = rvItem["exitcode"]
                exitcodeName = exitcodes.get(exitcode, str(exitcode))
                if rvItem["exitcode"] != 0 and rvItem["known_error"] == 0:
                    for i, rvStep in enumerate(rvItem["steps"]):
                        if rvStep["status"] == "FAILED":
                            webURL = f"http://cmssdt.cern.ch/SDT/cgi-bin/logreader/{arch}/{data['release_name']}/pyRelValMatrixLogs/run/{rvItem['id']}_{rvItem['name']}/step{i+1}_{rvItem['name']}.log"
                            # print(
                            #     f"\t\tRelVal {rvItem['id']} step {i+1} failed with {exitcode} ({exitcodeName})"
                            # )
                            log[arch].append(
                                f"| [{rvItem['id']}]({webURL}) | {exitcodeName} | ? |"
                            )
                            break
                    else:
                        print(
                            f"ERROR: RelVal {rvItem['id']} failed with {exitcodeName} at UNKNOWN step"
                        )

    print("=" * 80)

    os.mkdir("out")
    with open(f"out/{data['release_name']}_{ib_date}.md", "w") as f:
        print(f"## {data['release_name']}\n", file=f)
        print("-- INSERT SCREENSHOT HERE --\n", file=f)
        for arch, lines in log.items():
            print(f"### {arch}\n", file=f)
            print("\n".join(lines), file=f)
            print("", file=f)


def get_flavors(ib_date_in, cmssw_release=None):
    res = {}
    structure = fetch("SDT/html/data/structure.json")

    default_release = cmssw_release or structure["default_release"]

    all_releases = structure[default_release]

    # latest_ibs = fetch("SDT/html/data/LatestIBsSummary.json")
    for rel in all_releases:
        ib_data = fetch("SDT/html/data/" + rel + ".json")
        for comp in ib_data["comparisons"]:
            if comp["ib_date"] == ib_date_in and comp["isIB"]:
                res[rel] = comp
                break

    return res


def main():
    global exitcodes
    exitcodes_ = fetch("https://cms-sw.github.io/exitcodes.json")
    for k, v in exitcodes_.items():
        exitcodes[int(k)] = v
    # print(f"Loaded {len(exitcodes)} exit code(s)")
    structure = fetch("SDT/html/data/structure.json")

    if args.series == "default":
        default_release = structure["default_release"]
    else:
        default_release = args.series

    try:
        release_data = fetch("SDT/html/data/" + default_release + ".json")
    except urllib.error.HTTPError:
        print(f"!ERROR: Invalid release {default_release}!")
        exit(1)

    ib_dates = [] if args.date else args.date

    if not ib_dates:
        latest_ib_date, previous_ib_date = None, None

        for i, c in enumerate(release_data["comparisons"]):
            if not c["isIB"]:
                continue

            latest_ib_date = release_data["comparisons"][i]["ib_date"]
            try:
                previous_ib_date = release_data["comparisons"][i + 1]["ib_date"]
            except IndexError:
                pass

            break

        print(f"Latest IB date: {latest_ib_date}")
        print(f"Previous IB date: {previous_ib_date}")

        if latest_ib_date is None:
            print(f"!ERROR: latest IB for {default_release} not found!")
            exit(1)

        if previous_ib_date is None:
            print(f"?WARNING: only one IB available for {default_release}")

        ib_dates = [latest_ib_date]
        if previous_ib_date is not None:
            ib_dates.append(previous_ib_date)

    for ib_date in ib_dates:
        for flav, comp in get_flavors(ib_date, default_release).items():
            check_ib(comp)


# noinspection PyUnusedLocal
def main2():
    # /data/sdt/buildlogs/el8_amd64_gcc11/www/wed/13.2-wed-23/CMSSW_13_2_X_2023-05-10-2300/new/logAnalysis.pkl"
    summFile = "https://cmssdt.cern.ch/buildlogs/el8_amd64_gcc11/www/tue/13.2-tue-23/CMSSW_13_2_X_2023-05-09-2300/new/logAnalysis.pkl"
    summIO = io.BytesIO(fetch(summFile, content_type=ContentType.BINARY))
    summIO.seek(0)
    pklr = pickle.Unpickler(summIO)
    [rel, plat, anaTime] = pklr.load()
    print(f"{rel=}, {plat=}, {anaTime=}")
    errorKeys = pklr.load()
    # print(f"{errorKeys=}")
    nErrorInfo = pklr.load()
    # print(f"{nErrorInfo=}")
    errMapAll = pklr.load()
    # print(f"{errMapAll=}")
    packageList = pklr.load()
    # print(f"{packageList=}")
    topURL = pklr.load()
    # print(f"{topURL=}")
    errMap = pklr.load()
    # print(f"{errMap=}")
    tagList = pklr.load()
    # print(f"{tagList=}")
    pkgOK = pklr.load()
    # print(f"{pkgOK=}")
    summIO.close()

    url_prefix = f"https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/{plat}/{rel}"

    for pkg in [x for x in packageList if x.errInfo]:
        for err, cnt in pkg.errSummary.items():
            if err == "ignoreWarning":
                continue

            print(f"| [{pkg.name()}]({url_prefix}/{pkg.name()}) | {cnt}x {err} | TBD |")


def validate_date(x):
    if not (x == "auto" or date_rex.match(x.rsplit("_")[1])):
        raise ValueError()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="CMSSDT Shift Assistant")
    parser.add_argument(
        "-s",
        "--series",
        default="default",
        help="Release series to process or 'default' to use 'default_release' from structure.json",
    )
    parser.add_argument(
        "-d",
        "--date",
        default="auto",
        type=validate_date,
        help="IB date to process (YYYY-MM-DD) or 'auto' to process two last IBs",
        nargs="*",
    )
    args = parser.parse_args()
    # main2()
    main()
