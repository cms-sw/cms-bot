import datetime
import io
import json
import logging
import os
import pickle
import re
import time
import urllib
import urllib.error
import urllib.request
from collections import namedtuple
from enum import Enum

import github

import es_utils


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

g = None
repo_cache = {}
issue_cache = {}
localtz = None


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
    # print("Fetching", url)
    try:
        response = urllib.request.urlopen(url, timeout=10)
    except urllib.error.HTTPError as e:
        logger.fatal(
            f"Request to {url if isinstance(url, str) else url.full_url} failed with code {e.code}"
        )
        if e.code != 404:
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


def fetch_and_find(url, start_line, callback):
    url = make_url(url)
    try:
        with urllib.request.urlopen(url) as response:
            for current_line_number, line in enumerate(response, start=1):
                if current_line_number > start_line:
                    line = line.decode("utf-8").strip()
                    should_stop, res = callback(line)
                    if should_stop:
                        return res

    except urllib.error.URLError as e:
        print(f"An error occurred: {e}")
        return None

    return None


def extract_relval_error(release_name, arch, rvItem):
    def exception_message(line):
        if not hasattr(exception_message, "state"):
            exception_message.state = {"state": 0}
        if line.strip() == "Exception Message:" and exception_message.state["state"] == 0:
            exception_message.state["state"] = 1
            exception_message.state["data"] = []
            return False, None

        if "End Fatal Exception" in line:
            exception_message.state["state"] = 0
            return True, " ".join(exception_message.state["data"])

        if exception_message.state["state"] == 1:
            exception_message.state["data"].append(line.replace('"', ""))

        return False, None

    def first_valid_frame(line):
        def remove_templates(name):
            stack = []
            result = []
            last_index = 0

            for i, char in enumerate(name):
                if char == "<":
                    if not stack:
                        result.append(name[last_index:i])
                    stack.append("<")
                elif char == ">":
                    if stack:
                        stack.pop()
                        if not stack:
                            last_index = i + 1

            if not stack:
                result.append(name[last_index:])

            return "".join(result)

        if line.startswith("Thread") or (not line.strip()) or line.startswith("Current Modules:"):
            return True, "?"
        m = re.match(r"^#\d+\s+0x[0-9a-f]{16,16} in ([^?].+) from (.+)$", line)
        if not m:
            return False, None
        else:
            if ("cms/cmssw" not in m.group(2)) and ("at src/" not in m.group(2)):
                return False, None
            return True, remove_templates(m.group(1).strip())

    def parse_missing_product(line):
        if not hasattr(parse_missing_product, "state"):
            parse_missing_product.state = {"state": 0}
        if (
            line.strip() == "An exception of category 'ProductNotFound' occurred while"
            and parse_missing_product.state["state"] == 0
        ):
            parse_missing_product.state = {"state": 1}
        else:
            parse_missing_product.state = {"state": 2}

        if parse_missing_product.state["state"] == 1:
            m = re.match("^.*Calling method for module (.*)$", line)
            if m:
                parse_missing_product.state = {"method": m.group(1)}
                return False

            m = re.match("^Looking for type: (.*)$", line)
            if m:
                parse_missing_product.state["type"] = m.group(1)
                return False

            m = re.match("^Looking for module label: (.*)$", line)
            if m:
                parse_missing_product.state["label"] = m.group(1)
                return False

            m = re.match("^Looking for productInstanceName: (.*)$", line)
            if m:
                parse_missing_product.state["name"] = m.group(1)
                parse_missing_product.state["state"] = 0
                return True

        elif parse_missing_product.state["state"] == 2 and "End Fatal Exception " in line:
            parse_missing_product.state["state"] = 0
        return False

    def parse_asserion(line):
        m = re.search("Assertion `(.*)' failed", line)
        if m:
            return True, f"Assertion '{m.groups(1)[0]}' failed"
        else:
            return True, f"Unknown assertion"

    ret = []
    exitcode = rvItem["exitcode"]
    exitcodeName = exitcodes.get(exitcode, str(exitcode))
    if rvItem["exitcode"] != 0 and rvItem["known_error"] == 0:
        for i, rvStep in enumerate(rvItem["steps"]):
            if rvStep["status"] == "DAS_ERROR":
                return LogEntry(
                    name=f"Relval {rvItem['id']} step {i + 1}",
                    url="",
                    data={
                        "exit_code_name": "DAS_ERROR",
                        "workflow": rvItem["id"],
                        "step": 1,
                        "details": f"DAS ERROR in Relval {rvItem['id']}",
                    },
                )

            if rvStep["status"] in ("FAILED", "DAS_ERROR"):
                webURL = (
                    f"http://cmssdt.cern.ch/SDT/cgi-bin/logreader/"
                    f"{arch}/"
                    f"{release_name}/pyRelValMatrixLogs/run/"
                    f"{rvItem['id']}_{rvItem['name']}/step{i + 1}_"
                    f"{rvItem['name']}.log"
                )
                webURL_t = webURL + "#/{lineStart}-{lineEnd}"
                logURL = f"https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/raw/{arch}/{release_name}/pyRelValMatrixLogs/run/{rvItem['id']}_{rvItem['name']}/step{i + 1}_{rvItem['name']}.log"

                utlDataURL = f"https://cmssdt.cern.ch/SDT/cgi-bin/buildlogs/raw_read_config/{arch}/{release_name}/pyRelValMatrixLogs/run/{rvItem['id']}_{rvItem['name']}/"
                if exitcodeName == "TimeOut":
                    return LogEntry(
                        name=f"Relval {rvItem['id']} step {i + 1}",
                        url=webURL,
                        data={
                            "exit_code_name": "TimeOut",
                            "workflow": rvItem["id"],
                            "step": i,
                            "details": f"TimeOut in step {i+1}",
                        },
                    )

                if rvStep["status"] != "DAS_ERROR":
                    utlDataURL = utlDataURL + f"step{i + 1}_{rvItem['name']}.log"
                else:
                    utlDataURL = utlDataURL + f"step{i + 1}_dasquery.log"

                try:
                    utlData = fetch(utlDataURL)
                except urllib.error.HTTPError:
                    return LogEntry(
                        name=f"Relval {rvItem['id']} step {i + 1}",
                        url=webURL,
                        data={
                            "exit_code_name": exitcodeName,
                            "workflow": rvItem["id"],
                            "step": i + 1,
                            "details": f"Unknown failure in Relval {rvItem['id']} step {i + 1}",
                            "line": -1,
                        },
                    )
                for ctl in utlData["show_controls"]:
                    if ctl["name"] != "Issues":
                        continue
                    for obj in ctl["list"]:
                        if obj["name"].startswith("Segmentation fault"):
                            continue

                        if exitcodeName == "SIGSEGV":
                            if obj["name"].startswith("sig_dostack_then_abort"):
                                res = fetch_and_find(
                                    logURL, int(obj["lineStart"]), first_valid_frame
                                )
                                if res:
                                    if res.startswith("cling::"):
                                        res = "CLING"
                                    else:
                                        if res.startswith("("):
                                            res = "(" + re.split(r"[(<]", res, 1)[1]
                                        else:
                                            res = re.split(r"[(<]", res, 1)[0]
                                        res = "`" + res + "`"
                                    return LogEntry(
                                        name=f"Relval {rvItem['id']} step {i + 1}",
                                        url=webURL_t.format(**obj),
                                        data={
                                            "details": f"SIGSEGV in {res}",
                                            "workflow": rvItem["id"],
                                            "step": i + 1,
                                            "line": obj["lineStart"],
                                            "func": res,
                                            "exit_code_name": exitcodeName,
                                        },
                                    )
                            else:
                                continue

                        if exitcodeName == "OtherCMS":
                            if obj["name"].startswith("Mount failure"):
                                return LogEntry(
                                    name=f"Relval {rvItem['id']} step {i + 1}",
                                    url=webURL_t.format(**obj),
                                    data={
                                        "details": "Mount failure",
                                        "workflow": rvItem["id"],
                                        "step": i + 1,
                                        "line": obj["lineStart"],
                                        "exit_code_name": exitcodeName,
                                    },
                                )
                            elif "Fatal Exception" in obj["name"]:
                                res = fetch_and_find(
                                    logURL, int(obj["lineStart"]), exception_message
                                )
                                return LogEntry(
                                    name=f"Relval {rvItem['id']} step {i + 1}",
                                    url=webURL_t.format(**obj),
                                    data={
                                        "details": "Fatal exception: {0}".format(res or ""),
                                        "workflow": rvItem["id"],
                                        "step": i + 1,
                                        "line": obj["lineStart"],
                                        "exit_code_name": exitcodeName,
                                        "exception": res,
                                    },
                                )

                        if exitcodeName == "SIGABRT":
                            if obj["name"].startswith("Assertion failure"):
                                res = fetch_and_find(
                                    logURL, int(obj["lineStart"]) - 1, parse_asserion
                                )
                                return LogEntry(
                                    name=f"Relval {rvItem['id']} step {i + 1}",
                                    url=webURL_t.format(**obj),
                                    data={
                                        "details": res,
                                        "workflow": rvItem["id"],
                                        "step": i + 1,
                                        "exit_code_name": exitcodeName,
                                        "assertion": res,
                                    },
                                )
                            else:
                                continue

                        if exitcodeName == "ProductNotFound":
                            ret = fetch_and_find(logURL, int(obj["lineStart"]), first_valid_frame)
                            if ret:
                                state = getattr(parse_missing_product, "state", None)
                                if state:
                                    return LogEntry(
                                        name=f"Relval {rvItem['id']} step {i + 1}",
                                        url=webURL_t.format(**obj),
                                        data={
                                            "details": "Product {type} {name} missing in module {method}".format(
                                                **state
                                            ),
                                            "workflow": rvItem["id"],
                                            "step": i + 1,
                                            "line": obj["lineStart"],
                                            "exit_code_name": exitcodeName,
                                            "product_type": state["type"],
                                            "product_name": state["name"],
                                            "method": state["method"],
                                        },
                                    )

                        return LogEntry(
                            name=f"Relval {rvItem['id']} step {i + 1}",
                            url=webURL_t.format(**obj),
                            data={
                                "exit_code_name": exitcodeName,
                                "workflow": rvItem["id"],
                                "step": i + 1,
                                "line": obj["lineStart"],
                            },
                        )
                else:
                    return LogEntry(
                        name=f"Relval {rvItem['id']} step {i+1}",
                        url=webURL,
                        data={
                            "exit_code_name": exitcodeName,
                            "workflow": rvItem["id"],
                            "step": i + 1,
                            "line": -1,
                        },
                    )

    logger.error(
        f"RelVal {rvItem['id']} in IB {release_name} for {arch} failed with {exitcodeName} "
        f"at UNKNOWN step"
    )
    for i, rvStep in enumerate(rvItem["steps"]):
        print(f"Step {i} status {rvStep['status']}")

    return LogEntry(
        name=f"Relval {rvItem['id']} step UNKNOWN",
        url="",
        data={
            "exit_code_name": exitcodeName,
            "workflow": rvItem["id"],
            "step": -1,
        },
    )

    # print("!!!")


def check_ib(data, compilation_only=False):
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
            try:
                summIO = io.BytesIO(fetch(bldFile, content_type=ContentType.BINARY))
            except urllib.error.HTTPError:
                continue

            pklr = pickle.Unpickler(summIO)
            [rel, plat, _] = pklr.load()
            _ = pklr.load()
            _ = pklr.load()
            _ = pklr.load()
            packageList: List[PackageInfo] = pklr.load()
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

                # If there are compilation errors, only report those
                if pkg_errors.get("compError", 0) > 0:
                    res[arch]["build"].append(
                        LogEntry(
                            name=pkg.name(),
                            url=f"{url_prefix}/{pkg.name()}",
                            data=("compError", pkg_errors["compError"]),
                        )
                    )

                    continue

                for itm in pkg_errors.items():
                    res[arch]["build"].append(
                        LogEntry(name=pkg.name(), url=f"{url_prefix}/{pkg.name()}", data=itm)
                    )

    if not compilation_only:
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
                        try:
                            utlData = fetch(
                                f"SDT/cgi-bin/buildlogs/raw_read_config/{arch}/"
                                f"{data['release_name']}/unitTestLogs/{pkg}",
                                ContentType.JSON,
                            )
                        except urllib.error.HTTPError:
                            utlData = {"show_controls": []}

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
                try:
                    rvData = fetch(
                        f"SDT/public/cms-sw.github.io/data/relvals/{arch}/{ib_date}/"
                        f"{queue}.json",
                        ContentType.JSON,
                    )
                except urllib.error.HTTPError:
                    rvData = []

                for rvItem in rvData:
                    if rvItem["exitcode"] == 0 or rvItem["known_error"] == 1:
                        continue
                    x = extract_relval_error(data["release_name"], arch, rvItem)
                    assert x
                    res[arch]["relval"].append(x)
    logger.info("=" * 80)
    return data["release_name"], res


def get_ib_results(ib_date, flavor, ib_data=None):
    if len(ib_date.split("-")) > 4:
        short_ib_date = "-".join(ib_date.split("-", 5)[:-1])
    else:
        short_ib_date = ib_date
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


def parse_config_line(line):
    res = {}
    data = [x.strip() for x in line.split(";") if x.strip()]
    for var in data:
        k, v = var.split("=")
        try:
            v = int(v)
        except ValueError:
            pass

        if isinstance(v, str):
            tmp = v.split(",")
            if len(tmp) > 1:
                res[k] = []
                for itm in tmp:
                    try:
                        itm = int(itm)
                    except ValueError:
                        pass

                    res[k].append(itm)
            else:
                res[k] = v

    return res


def get_expected_ibs(series, ib_date):
    res = []
    y, m, d, h = (int(x) for x in ib_date.split("-"))
    h = int(h) // 100
    d = datetime.date(y, m, d)
    wd = d.isoweekday() % 7  # to make Sunday = 0

    cms_bot_dir = os.getenv("CMS_BOT_DIR", os.path.dirname(os.path.dirname(__file__)))
    with open(os.path.join(cms_bot_dir, "config.map"), "r") as f:
        for line in f:
            data = parse_config_line(line)
            if (
                data["CMSDIST_TAG"].startswith("IB/" + series)
                and data.get("DISABLED", 0) == 0
                and h in data.get("BUILD_HOUR", (11, 23))
                and wd in data.get("BUILD_DAY", (0, 1, 2, 3, 4, 5, 6))
            ):
                res.append((data["RELEASE_QUEUE"], data["SCRAM_ARCH"]))

    return res


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
    ret = es_utils.es_query(
        f"cmssdt-{index}-failures", query, start_time=0, end_time=1000 * int(time.time())
    )
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


def setup_github():
    global g, localtz
    localtz = currenttz()

    if github:
        g = github.Github(
            login_or_token=open(os.path.expanduser("~/.github-token")).read().strip()
        )
    else:
        g = None
