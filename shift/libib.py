import datetime
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
        if "Error" in errInfo.errType:
            self.warnOnly = False
        self.errInfo.append(errInfo)
        if errInfo.errType not in self.errSummary.keys():
            self.errSummary[errInfo.errType] = 1
        else:
            self.errSummary[errInfo.errType] += 1
        self.errLines[lineNo] = errInfo.errType

    def name(self):
        """docstring for name"""
        return self.subsys + "/" + self.pkg


url_root = "https://cmssdt.cern.ch/"
exitcodes = {}
logger = logging.Logger("libib", logging.INFO)
date_rex = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})00")


class ContentType(Enum):
    JSON = 1
    TEXT = 2
    BINARY = 3


LogEntry = namedtuple("LogEntry", "name,url,data")


def date_fromisoformat(date_str):
    if date_str.endswith("Z"):
        tzinfo = datetime.timezone.utc
        date_str = date_str.rstrip("Z")
    else:
        tzinfo = None

    date_str, time_str = date_str.split("T")
    date_y, date_m, date_d = date_str.split("-")
    time_h, time_m, time_s = time_str.split(":")

    return datetime.datetime(
        year=int(date_y),
        month=int(date_m),
        day=int(date_d),
        hour=int(time_h),
        minute=int(time_m),
        second=int(time_s),
        tzinfo=tzinfo,
    )


def date_fromibdate(date_str):
    y, m, d, h = (int(x) for x in date_rex.findall(date_str)[0])
    return datetime.datetime(year=y, month=m, day=d, hour=h)


def setup_logging(level=logging.INFO):
    global logger
    logger = logging.getLogger("libib")
    logger.setLevel(level)


def make_url(url):
    if not isinstance(url, str):
        return url
    url = url.lstrip("/")
    if url.startswith("http"):
        return url
    else:
        return url_root + url


def fetch(url, content_type=ContentType.JSON, payload=None):
    url = make_url(url)
    try:
        response = urllib.request.urlopen(url, timeout=10)
    except urllib.error.HTTPError as e:
        logger.fatal(
            f"Request to {url if isinstance(url, str) else url.full_url} failed with code {e.code}"
        )
        logger.fatal(f"{e.read()}")
        raise
    except urllib.error.URLError as e:
        logger.fatal(
            f"Request to {url if isinstance(url, str) else url.full_url} failed with error {e.reason}"
        )
        raise
    if response.getcode() != 200:
        logger.fatal(
            f"Request to {url if isinstance(url, str) else url.full_url} failed with code {response.getcode()}"
        )
        raise RuntimeError()

    content = response.read()
    if payload is None:
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
                pkg_errors = dict(
                    (
                        (err, cnt)
                        for err, cnt in pkg.errSummary.items()
                        if err != "ignoreWarning" and cnt > 0
                    )
                )
                for itm in pkg_errors.items():
                    res[arch]["build"].append(
                        LogEntry(
                            name=pkg.name(), url=f"{url_prefix}/{pkg.name()}", data=itm
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


def get_ib_results(ib_date, flavor, ib_data=None):
    short_ib_date = ib_date.rsplit("-", 1)[0]
    ib_data = ib_data or fetch("SDT/html/data/" + flavor + ".json")
    for comp in ib_data["comparisons"]:
        comp_ib_date = comp["ib_date"].rsplit("-", 1)[0]
        if short_ib_date == comp_ib_date and comp["isIB"]:
            return comp


def get_ib_comparision(ib_date, series):
    res = {}
    structure = fetch("SDT/html/data/structure.json")
    all_releases = structure[series]

    for rel in all_releases:
        res[rel] = get_ib_results(ib_date, rel)

    return res


def get_ib_dates(cmssw_release):
    structure = fetch("SDT/html/data/structure.json")

    if cmssw_release == "default":
        default_release = structure["default_release"]
    else:
        default_release = cmssw_release

    try:
        release_data = fetch("SDT/html/data/" + default_release + ".json")
    except urllib.error.HTTPError:
        print(f"!ERROR: Invalid release {default_release}!")
        exit(1)

    latest_ib_date, previous_ib_date = None, None

    for i, c in enumerate(release_data["comparisons"]):
        if not c["isIB"]:
            continue

        latest_ib_date = release_data["comparisons"][i]["ib_date"]
        try:
            previous_ib_date = release_data["comparisons"][i + 1]["ib_date"]
        except IndexError:
            pass

        if previous_ib_date:
            previous_ib_datetime = date_fromibdate(previous_ib_date)
            now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
            if (now - previous_ib_datetime).seconds > 24 * 3600:
                print(f"Previous IB {previous_ib_date} is more than 24h old, ignoring")
                previous_ib_date = None

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

    return ib_dates
