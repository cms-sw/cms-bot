"""Scan an unpacked IB test-log zip where cms-bot already unpacked it, and
write the result next to the zip.

Meant to be called from cms-bot's es_ibs_log.py, right after it unzips
unitTestLogs.zip into UT/ or addOnTests.zip into AO/:

    scan_unit_test_dir(utdir + "/UT", zip_path=logFile)
    scan_addon_dir(utdir + "/AO", zip_path=logFile)

and from jenkins-jobs/process-relval-logs (bash), when the RelVals of a build
are finished, after its clean-up and before it zips the folder:

    python3 ib_test_log_problems.py relval "$dir" || true

Each call writes one file in the zip's folder (the build folder):

    unitTestLogs.zip                     -> unitTestLogs-scan.json.gz
    addOnTests.zip                       -> addOnTests-scan.json.gz
    pyRelValPartialLogs/ (before the zip) -> pyRelValMatrixLogs-scan.json.gz

DBG RelVals are never zipped but still reach that point.
They are SKIPPED for now: one DBG RelVal folder is ~220 GB (each step log twice,
~117 GB unique), hours of reading inside their job. Set TEST_LOG_SCAN_DBG_RELVAL=1
to scan them (a later step). DBG unit tests / addOn are still scanned.

The file holds every test with its status, every problem found in the logs
(ib_test_log_scanner.py does the detection), and a `source` block saying which
build it belongs to (IB tag, architecture, variant, queue), read from the zip
path. It is the same format as the cmssdt-kg-chatbot results files, so its
importer (ingest_test_logs.py) reads it unchanged.

Rules this file keeps, because it runs inside someone else's job:
  * standard library only, Python 3.8+;
  * no network, no database, no credentials -- it only reads the unpacked
    logs and writes one file;
  * never writes inside the unpacked folder (cms-bot zips that folder again);
  * the result is written to "<name>.tmp" and renamed, so nobody ever sees a
    half-written file;
  * a zip path that does not look like a build folder raises ValueError and
    writes nothing, rather than guessing which build it is. The caller wraps
    each call in try/except, so an error here never stops cms-bot's own work.

Calling it again for the same zip simply rewrites the same file.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time

import ib_test_log_scanner as scanner

# <arch>/www/<day>/<queue>/<IB tag>/[gpu/<card>/|other/<name>/]<zip>
PATH_RE = re.compile(
    r"(?:^|/)(?P<arch>[^/]+)/www/(?P<day>[^/]+)/(?P<queue>[^/]+)/(?P<tag>CMSSW_[^/]+)/(?P<rest>[^/].*)$"
)
ZIP_KINDS = {
    "unitTestLogs.zip": "unit",
    "addOnTests.zip": "addon",
    "pyRelValMatrixLogs.zip": "relval",
}
DBG_RELVAL_ENV = "TEST_LOG_SCAN_DBG_RELVAL"  # =1 scans DBG RelVals too (off for now, ~220 GB each)
RELVAL_DIR = "pyRelValPartialLogs"  # what process-relval-logs zips into pyRelValMatrixLogs.zip
RELVAL_DONE_RE = re.compile(r"^done\.")
RELVAL_TOTAL_RE = re.compile(r"^done\.\d+of(\d+)$")
EVIDENCE_LINES_QUIET = (
    8  # evidence lines kept for message_logger / generic records (as the chatbot's fetcher)
)


def describe_zip_path(zip_path: str) -> dict:
    """Which build a zip belongs to, from its path. Raises ValueError if the
    path does not have the build-folder shape."""
    path = os.path.abspath(zip_path).replace(os.sep, "/")
    m = PATH_RE.search(path)
    name = path.rsplit("/", 1)[-1]
    if not m or name not in ZIP_KINDS:
        raise ValueError(f"not an IB test-log zip path: {zip_path}")
    rest = m.group("rest")
    parts = rest.split("/")
    if len(parts) == 1:
        variant = ""
    elif len(parts) == 3 and parts[0] in ("gpu", "other"):
        variant = "/".join(parts[:2])
    else:
        raise ValueError(f"unexpected folder below the IB tag in {zip_path}")
    rel = path[m.start("arch") :]
    return dict(
        kind=ZIP_KINDS[name],
        arch=m.group("arch"),
        tag=m.group("tag"),
        variant=variant,
        queue=m.group("queue"),
        path=rel,
    )


def scan_file_path(zip_path: str) -> str:
    """unitTestLogs.zip -> unitTestLogs-scan.json.gz, in the same folder."""
    folder, name = os.path.split(zip_path)
    return os.path.join(folder, name[: -len(".zip")] + "-scan.json.gz")


def _trim(problem: dict) -> dict:
    if problem["kind"] not in scanner.SERIOUS_KINDS:
        problem = dict(problem, block=problem["block"][:EVIDENCE_LINES_QUIET])
    return problem


def _write(
    result: dict,
    source: dict,
    zip_path: str,
    out_path: str | None,
    size: int | None = None,
    mtime: float | None = None,
) -> str:
    if size is None or mtime is None:
        st = os.stat(zip_path)
        size, mtime = st.st_size, st.st_mtime
    result["problems"] = [_trim(p) for p in result["problems"]]
    result["source"] = dict(
        source,
        size=size,
        mtime=mtime,
        scanned_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        scanner_version=scanner.SCANNER_VERSION,
        scanned_by="ib_test_log_problems",
    )
    out_path = out_path or scan_file_path(zip_path)
    tmp = out_path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        json.dump(result, fh, default=str)
    os.replace(tmp, out_path)
    return out_path


def _check_dir(unpacked_dir: str) -> None:
    if not os.path.isdir(unpacked_dir):
        raise ValueError(f"unpacked folder does not exist: {unpacked_dir}")


def scan_unit_test_dir(unpacked_dir: str, zip_path: str, out_path: str | None = None) -> str:
    """Scans the unpacked unitTestLogs.zip in `unpacked_dir` (cms-bot's UT/).
    Returns the path of the file written."""
    source = describe_zip_path(zip_path)
    if source["kind"] != "unit":
        raise ValueError(f"not a unit-test zip: {zip_path}")
    _check_dir(unpacked_dir)
    return _write(scanner.scan_unit_test_dir(unpacked_dir), source, zip_path, out_path)


def scan_addon_dir(
    unpacked_dir: str, zip_path: str, addon_log: str | None = None, out_path: str | None = None
) -> str:
    """Scans the unpacked addOnTests.zip in `unpacked_dir` (cms-bot's AO/).
    Each test's pass/fail comes from addOnTests.log, by default the one next
    to the zip. Returns the path of the file written."""
    source = describe_zip_path(zip_path)
    if source["kind"] != "addon":
        raise ValueError(f"not an addOn zip: {zip_path}")
    _check_dir(unpacked_dir)
    addon_log = addon_log or os.path.join(os.path.dirname(zip_path), "addOnTests.log")
    with open(addon_log, encoding="utf-8", errors="replace") as fh:
        addon_log_text = fh.read()
    return _write(scanner.scan_addon_dir(unpacked_dir, addon_log_text), source, zip_path, out_path)


def relval_progress(partial_logs_dir: str, earlier_jobs: list[str] | None = None) -> dict:
    """How many RelVal jobs reported back, counted like process-relval-logs:
    every done.* file is one job, the total is N of the last done.<i>of<N> in
    `ls` order. complete=False means cms-bot zips it after its 10-hour wait
    with jobs missing. `earlier_jobs` (from an earlier scan of the same build)
    are counted too, so a job that came back later completes the run."""
    names = sorted(
        set(n for n in os.listdir(partial_logs_dir) if RELVAL_DONE_RE.match(n))
        | set(earlier_jobs or [])
    )
    totals = [m.group(1) for m in map(RELVAL_TOTAL_RE.match, names) if m]
    total = int(totals[-1]) if totals else None
    return dict(
        jobs=names,
        jobs_done=len(names),
        jobs_total=total,
        complete=total is not None and len(names) == total,
    )


def _earlier_relval_scan(out_path: str, tag: str) -> dict | None:
    """The scan file an earlier run of process-relval-logs wrote for this build,
    if any. It only exists when cms-bot processed the build twice: a job came
    back after the folder was zipped and renamed, so the new folder holds only
    that job's workflows."""
    try:
        with gzip.open(out_path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    source = data.get("source") or {}
    if data.get("kind") != "relval" or source.get("tag") != tag or not source.get("jobs"):
        return None
    return data


def _merge_relval(new: dict, old: dict) -> dict:
    """Workflows scanned now replace the same workflows from the earlier scan;
    the earlier scan's other workflows and their problems are kept."""
    now = {w["workflow"] for w in new["workflows"]}
    new["workflows"] = sorted(
        [w for w in old["workflows"] if w["workflow"] not in now] + new["workflows"],
        key=lambda w: w["workflow"],
    )
    new["problems"] = [p for p in old["problems"] if p.get("workflow") not in now] + new[
        "problems"
    ]
    return new


def scan_relval_dir(partial_logs_dir: str, out_path: str | None = None) -> str:
    """Scans <build>/[gpu/<card>/|other/<name>/]pyRelValPartialLogs/ -- the
    folder process-relval-logs is about to zip -- and writes
    pyRelValMatrixLogs-scan.json.gz next to it. Works when there is no zip
    yet (or never will be, DBG). Returns the path of the file written."""
    folder = os.path.abspath(partial_logs_dir).rstrip("/")
    if os.path.basename(folder) != RELVAL_DIR:
        raise ValueError(f"not a {RELVAL_DIR} folder: {partial_logs_dir}")
    _check_dir(folder)
    zip_path = os.path.join(
        os.path.dirname(folder), "pyRelValMatrixLogs.zip"
    )  # where cms-bot puts the zip
    source = describe_zip_path(zip_path)
    earlier = _earlier_relval_scan(out_path or scan_file_path(zip_path), source["tag"])
    source = dict(
        source,
        scanned_from=RELVAL_DIR,
        **relval_progress(folder, earlier["source"]["jobs"] if earlier else None),
    )
    size = 0
    for dirpath, _, files in os.walk(folder):
        size += sum(os.path.getsize(os.path.join(dirpath, f)) for f in files)
    result = scanner.scan_relval_dir(folder)
    if earlier:
        result = _merge_relval(result, earlier)
        source["merged_with_scan_of"] = earlier["source"].get("scanned_at")
        size += earlier["source"].get("size") or 0
    return _write(result, source, zip_path, out_path, size=size, mtime=os.stat(folder).st_mtime)


def main(argv: list[str]) -> int:
    """By hand, or from process-relval-logs:
    ib_test_log_problems.py <unpacked dir> <zip path> [<out path>]   unit tests / addOn
    ib_test_log_problems.py relval <pyRelValPartialLogs dir> [<out path>]"""
    if len(argv) in (3, 4) and argv[1] == "relval":
        if "_DBG_X_" in os.path.abspath(argv[2]) and os.environ.get(DBG_RELVAL_ENV) != "1":
            print(f"skipped DBG RelVals {argv[2]} (off for now; {DBG_RELVAL_ENV}=1 scans them)")
            return 0
        started = time.time()
        out = scan_relval_dir(argv[2], out_path=argv[3] if len(argv) == 4 else None)
        print(f"wrote {out} in {time.time() - started:.1f} s")
        return 0
    if len(argv) not in (3, 4):
        print(main.__doc__)
        return 2
    unpacked_dir, zip_path = argv[1], argv[2]
    out_path = argv[3] if len(argv) == 4 else None
    started = time.time()
    if describe_zip_path(zip_path)["kind"] == "unit":
        out = scan_unit_test_dir(unpacked_dir, zip_path, out_path=out_path)
    else:
        out = scan_addon_dir(unpacked_dir, zip_path, out_path=out_path)
    print(f"wrote {out} in {time.time() - started:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
