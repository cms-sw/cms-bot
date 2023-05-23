import io
import json
import logging
import pickle
import re
import urllib
import urllib.error
import urllib.request
from collections import namedtuple
from enum import Enum


# Borrowed from https://github.com/cms-sw/cmssdt-web
class ErrorInfo(object):
    """keeps track of information for errors"""

    def __init__(self, errType, msg):
        super(ErrorInfo, self).__init__()
        self.errType = errType
        self.errMsg = msg


class PackageInfo(object):
    """keeps track of information for each package"""

    def __init__(self, subsys, pkg):
        super(PackageInfo, self).__init__()

        self.subsys = subsys
        self.pkg = pkg
        self.errInfo = []
        self.errSummary = {}
        self.errLines = {}
        self.warnOnly = True

    def addErrInfo(self, errInfo, lineNo):
        """docstring for addErr"""
        if 'Error' in errInfo.errType: self.warnOnly = False
        self.errInfo.append(errInfo)
        if errInfo.errType not in self.errSummary.keys():
            self.errSummary[errInfo.errType] = 1
        else:
            self.errSummary[errInfo.errType] += 1
        self.errLines[lineNo] = errInfo.errType

    def name(self):
        """docstring for name"""
        return self.subsys + '/' + self.pkg


url_root = "https://cmssdt.cern.ch/"
exitcodes = {}
logger = logging.Logger("libib", logging.INFO)


class ContentType(Enum):
    JSON = 1
    TEXT = 2
    BINARY = 3


LogEntry = namedtuple("LogEntry", "name,url,data")


def setup_logging():
    global logger
    logger = logging.getLogger("libib")


def make_url(url):
    if not isinstance(url, str):
        return url
    url = url.lstrip("/")
    if url.startswith("http"):
        return url
    else:
        return url_root + url


def fetch(url, payload=None, content_type=ContentType.JSON):
    url = make_url(url)
    try:
        response = urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        logger.fatal(f"Request to {url} failed with code {e.code}")
        logger.fatal(f"{e.read()}")
        raise
    except urllib.error.URLError as e:
        logger.fatal(f"Request to {url} failed with error {e.reason}")
        raise
    if response.getcode() != 200:
        logger.fatal(f"Request to {url} failed with code {response.getcode()}")
        raise RuntimeError()

    if payload is None:
        content = response.read()
        if content_type == ContentType.JSON:
            return json.loads(content)
        elif content_type == ContentType.TEXT:
            return content.decode("utf-8")
        else:
            return content


def get_exitcodes():
    global exitcodes
    exitcodes_ = fetch("https://cms-sw.github.io/exitcodes.json")
    for k, v in exitcodes_.items():
        exitcodes[int(k)] = v


def check_ib(data):
    global logger
    res = {}
    logger.info(f"Found IB {data['release_name']}")
    ib_date = data["ib_date"].rsplit("-", 1)[0]
    queue = data["release_queue"]
    for arch in data["tests_archs"]:
        # print(f"\tFound arch {arch}")
        res[arch] = {"build": [], "utest": [], "relval": []}

    logger.info("== Compilation results ==")
    for bld in data["builds"]:
        arch = bld["arch"]
        logger.info(f"\tArch: {arch}, status: {bld['passed']}")
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
                errors = [
                    (err, cnt)
                    for err, cnt in pkg.errSummary.items()
                    if err != "ignoreWarning" and cnt > 0
                ]

                res[arch]["build"].append(
                    LogEntry(
                        name=pkg.name, url=f"{url_prefix}/{pkg.name()}", data=errors
                    )
                )

    logger.info("== Unit test results ==")
    for ut in data["utests"]:
        arch = ut["arch"]
        logger.info(f"\tArch: {arch}, status: {ut['passed']}")
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
                    webURL_t = (
                        f"https://cmssdt.cern.ch/SDT/cgi-bin/logreader/"
                        f"{arch}/{data['release_name']}/unitTestLogs/{pkg}#/{{"
                        f"lineStart}}-{{lineEnd}}"
                    )
                    # print(f"\t\t{failed} Unit Test{'s' if failed>1 else ''} in {pkg}")
                    utlData = fetch(
                        f"SDT/cgi-bin/buildlogs/raw_read_config/{arch}/"
                        f"{data['release_name']}/unitTestLogs/{pkg}",
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
                                res[arch]["utest"].append(
                                    LogEntry(name=utName, url=webURL, data=None)
                                )

    logger.info("== RelVal results ==")
    for rv in data["relvals"]:
        arch = rv["arch"]
        logger.info(f"\tArch: {rv['arch']}, status: {rv['passed']}")
        if not rv["passed"]:
            rvData = fetch(
                f"SDT/public/cms-sw.github.io/data/relvals/{arch}/{ib_date}/"
                f"{queue}.json",
                ContentType.JSON,
            )
            for rvItem in rvData:
                exitcode = rvItem["exitcode"]
                exitcodeName = exitcodes.get(exitcode, str(exitcode))
                if rvItem["exitcode"] != 0 and rvItem["known_error"] == 0:
                    for i, rvStep in enumerate(rvItem["steps"]):
                        if rvStep["status"] == "FAILED":
                            webURL = (
                                f"http://cmssdt.cern.ch/SDT/cgi-bin/logreader/"
                                f"{arch}/"
                                f"{data['release_name']}/pyRelValMatrixLogs/run/"
                                f"{rvItem['id']}_{rvItem['name']}/step{i + 1}_"
                                f"{rvItem['name']}.log"
                            )
                            res[arch]["relval"].append(
                                LogEntry(
                                    name=f"Relval" f" {rvItem['id']} step {i + 1}",
                                    url=webURL,
                                    data=exitcodeName,
                                )
                            )
                            break
                    else:
                        logger.error(
                            f"ERROR: RelVal {rvItem['id']} failed with {exitcodeName} "
                            f"at UNKNOWN step"
                        )

    logger.info("=" * 80)
    return data["release_name"], res
    #
    # os.makedirs("out", exist_ok=True)
    # with open(f"out/{data['release_name']}_{ib_date}.md", "w") as f:
    #     print(f"## {data['release_name']}\n", file=f)
    #     print("-- INSERT SCREENSHOT HERE --\n", file=f)
    #     for arch, lines in log.items():
    #         print(f"### {arch}\n", file=f)
    #         if lines:
    #             lines = [
    #                         "| What failed | Description | Issue |",
    #                         "| ----------- | ----------- | ----- |",
    #                     ] + lines
    #             print("\n".join(lines), file=f)
    #         else:
    #             print('<span style="color:green">No issues</span>', file=f)
    #         print("", file=f)


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
