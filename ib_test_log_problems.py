"""Scan IB test logs where cms-bot already has them, for the IB chatbot.

Called from cms-bot in two places:

  es_ibs_log.py, right after it unzips unitTestLogs.zip into UT/ or
  addOnTests.zip into AO/:

      scan_unit_test_dir(utdir + "/UT", zip_path=logFile)
      scan_addon_dir(utdir + "/AO", zip_path=logFile)

  runPyRelValThread.py parseLog, for every RelVal step log it has not
  processed yet, just before es_parse_log:

      write_relval_step_scan(logFile)

What they write, in the outbox /data/sdt/chatbot-outbox (env CHATBOT_OUTBOX):

    unit/    unit__<arch>__<tag>__<variant>.json.gz                        one per zip
    addon/   addon__<arch>__<tag>__<variant>.json.gz                       one per zip
    relval/  relval__<arch>__<tag>__<variant>__<workflow>__stepN.json.gz   one per step

<variant> is "main", gpu_<card> or other_<name>. A separate job sends the files and
deletes them. The outbox itself is never created here (only its sub-folders); that job
creates it and renews its modification time on every run. Without the folder, or when
the job has not run for a day, nothing is scanned: no job, no files piling up. DBG RelVals are skipped (one run is ~117 GB of logs, hours of
checking); DBG unit tests / addOn are scanned.

The files hold every test / step with its status and every problem found in
its logs (ib_test_log_scanner.py does the detection).

Rules this file keeps, because it runs inside someone else's job:
  * standard library only, Python 3.8+;
  * no network, no database, no credentials -- it only reads logs and writes
    its own files;
  * never writes inside the unpacked / pyRelValPartialLogs folder;
  * every file is written to "<name>.tmp" and renamed, so nobody ever sees a
    half-written file;
  * a path that does not look like a build folder raises ValueError and writes
    nothing, rather than guessing which build it is. The caller wraps each
    call in try/except, so an error here never stops cms-bot's own work.

Calling it again for the same logs simply rewrites the same file.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
import time
import zlib

import ib_test_log_scanner as scanner

# <arch>/www/<day>/<queue>/<IB tag>/[gpu/<card>/|other/<name>/]<zip>
PATH_RE = re.compile(
    r"(?:^|/)(?P<arch>[^/]+)/www/(?P<day>[^/]+)/(?P<queue>[^/]+)/(?P<tag>CMSSW_[^/]+)/(?P<rest>[^/].*)$"
)
ZIP_KINDS = {"unitTestLogs.zip": "unit", "addOnTests.zip": "addon"}
RELVAL_DIR = "pyRelValPartialLogs"
STEP_RE = re.compile(r"^step(\d+)_.*\.log$")  # the logs parseLog processes
OUTBOX = os.environ.get("CHATBOT_OUTBOX", "/data/sdt/chatbot-outbox")
SENDER_ALIVE_HOURS = 24
COPY_CHECK_BYTES = 1 << 20  # equal size + equal first and last MB = the same log
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


def scan_file_name(where: dict, kind: str) -> str:
    """unit__<arch>__<tag>__<variant or main>.json.gz (RelVal steps add workflow and step)."""
    variant = where["variant"].replace("/", "_") or "main"
    parts = [kind, where["arch"], where["tag"], variant]
    if kind == "relval":
        parts += [where["workflow"], f"step{where['step']}"]
    return "__".join(parts) + ".json.gz"


def _trim(problem: dict) -> dict:
    if problem["kind"] not in scanner.SERIOUS_KINDS:
        problem = dict(problem, block=problem["block"][:EVIDENCE_LINES_QUIET])
    return problem


def _write_json(doc: dict, out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = out_path + ".tmp"
    try:
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump(doc, fh, default=str)
        os.replace(tmp, out_path)
    except BaseException:  # disk full, job stopped: no half-written file stays behind
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return out_path


def _write(result: dict, source: dict, zip_path: str, out_path: str) -> str:
    st = os.stat(zip_path)
    result["problems"] = [_trim(p) for p in result["problems"]]
    result["source"] = dict(
        source,
        size=st.st_size,
        mtime=st.st_mtime,
        scanned_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        scanner_version=scanner.SCANNER_VERSION,
        scanned_by="ib_test_log_problems",
    )
    return _write_json(result, out_path)


def outbox_open(outbox: str) -> bool:
    """Whether the sender is there to take the files (see the module docstring)."""
    try:
        return time.time() - os.stat(os.path.join(outbox, "")).st_mtime < SENDER_ALIVE_HOURS * 3600
    except OSError:
        return False


def _out_path(source: dict, out_path: str | None) -> str | None:
    """Where a unit/addOn result goes: `out_path`, else the outbox; None = not open, do not scan."""
    if out_path:
        return out_path
    if not outbox_open(OUTBOX):
        return None
    return os.path.join(OUTBOX, source["kind"], scan_file_name(source, source["kind"]))


def _check_dir(unpacked_dir: str) -> None:
    if not os.path.isdir(unpacked_dir):
        raise ValueError(f"unpacked folder does not exist: {unpacked_dir}")


def scan_unit_test_dir(
    unpacked_dir: str, zip_path: str, out_path: str | None = None
) -> str | None:
    """Scans the unpacked unitTestLogs.zip in `unpacked_dir` (cms-bot's UT/).
    Returns the path of the file written, None if there is no outbox."""
    source = describe_zip_path(zip_path)
    if source["kind"] != "unit":
        raise ValueError(f"not a unit-test zip: {zip_path}")
    out_path = _out_path(source, out_path)
    if not out_path:
        return None
    _check_dir(unpacked_dir)
    return _write(scanner.scan_unit_test_dir(unpacked_dir), source, zip_path, out_path)


def scan_addon_dir(
    unpacked_dir: str, zip_path: str, addon_log: str | None = None, out_path: str | None = None
) -> str | None:
    """Scans the unpacked addOnTests.zip in `unpacked_dir` (cms-bot's AO/).
    Each test's pass/fail comes from addOnTests.log, by default the one next
    to the zip. Returns the path of the file written, None if there is no outbox."""
    source = describe_zip_path(zip_path)
    if source["kind"] != "addon":
        raise ValueError(f"not an addOn zip: {zip_path}")
    out_path = _out_path(source, out_path)
    if not out_path:
        return None
    _check_dir(unpacked_dir)
    addon_log = addon_log or os.path.join(os.path.dirname(zip_path), "addOnTests.log")
    with open(addon_log, encoding="utf-8", errors="replace") as fh:
        addon_log_text = fh.read()
    return _write(scanner.scan_addon_dir(unpacked_dir, addon_log_text), source, zip_path, out_path)


def describe_step_log(log_file: str) -> dict:
    """Which build, workflow and step a RelVal step log belongs to:
    <arch>/www/<day>/<queue>/<tag>/[gpu/<card>/|other/<name>/]pyRelValPartialLogs/<workflow>/stepN_*.log
    """
    path = os.path.abspath(log_file).replace(os.sep, "/")
    m = PATH_RE.search(path)
    rest = m.group("rest").split("/") if m else []
    step = STEP_RE.match(rest[-1]) if rest else None
    if len(rest) < 3 or rest[-3] != RELVAL_DIR or not step:
        raise ValueError(f"not a RelVal step log: {log_file}")
    variant = rest[:-3]
    if variant and (len(variant) != 2 or variant[0] not in ("gpu", "other")):
        raise ValueError(f"unexpected folder below the IB tag in {log_file}")
    return dict(
        arch=m.group("arch"),
        tag=m.group("tag"),
        variant="/".join(variant),
        queue=m.group("queue"),
        path="/".join(
            [path[m.start("arch") : m.start("rest") - 1], *variant, "pyRelValMatrixLogs.zip"]
        ),
        workflow=rest[-2],
        step=int(step.group(1)),
    )


class _StepLog(scanner._RelvalDiskFile):
    """A step log, with a cheap crc(): cms-bot keeps stepN.log as a copy of the
    named step log, and reading a 2 GB log again to see that is not worth it."""

    def crc(self) -> int:
        if self._crc is None:
            with open(self.path, "rb") as fh:
                head = fh.read(COPY_CHECK_BYTES)
                if self.size > 2 * COPY_CHECK_BYTES:
                    fh.seek(-COPY_CHECK_BYTES, os.SEEK_END)
                self._crc = zlib.crc32(fh.read(), zlib.crc32(head))
        return self._crc


def _logs_of_step(wf_dir: str, step: int) -> list[str]:
    """The logs scanned together with this step. parseLog calls us only for steps
    that have a stepN_<something>.log; every other log of the workflow
    (das-up-to-nevents.log, a stepN.log without a named one) goes with the first
    such step >= 1, so each log belongs to exactly one step."""
    logs = [
        n
        for n in os.listdir(wf_dir)
        if n.endswith(".log") and n not in ("workflow.log", "time.log")
    ]
    called = {int(m.group(1)) for m in map(STEP_RE.match, logs) if m}
    first = min((s for s in called if s >= 1), default=min(called, default=step))
    out = []
    for name in logs:
        m = re.match(r"step(\d+)", name)
        owner = int(m.group(1)) if m and int(m.group(1)) in called else first
        if owner == step:
            out.append(name)
    return out


def write_relval_step_scan(log_file: str, outbox: str | None = None) -> str | None:
    """Scans one RelVal step (the log parseLog is about to process, its copies
    and das/lumi logs) and writes one file to the outbox. Returns its path, or
    None if nothing was scanned (DBG, or the outbox is not open).

    If the scan itself fails, the file says so (`scan_error`), because parseLog
    does not come back to this log: without it the step would look clean."""
    outbox = outbox or OUTBOX
    if "_DBG_X_" in log_file or not outbox_open(outbox):
        return None
    where = describe_step_log(log_file)
    wf_dir = os.path.dirname(os.path.abspath(log_file))
    st = os.stat(log_file)
    doc = dict(
        kind="relval_step",
        **where,
        status=None,
        exit_code=None,
        workflow_steps={},
        workflow_exit_codes=[],
        problems=[],
        log_mtime=st.st_mtime,
        scanned_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        scanner_version=scanner.SCANNER_VERSION,
        scanned_by="ib_test_log_problems",
    )
    try:
        wf, step = where["workflow"], where["step"]
        names = _logs_of_step(wf_dir, step)
        if os.path.exists(os.path.join(wf_dir, "workflow.log")):
            names.append("workflow.log")
        result = scanner._scan_relval_members(
            [_StepLog(os.path.join(wf_dir, n), f"{wf}/{n}") for n in names]
        )
        info = result["workflows"][0]
        codes = info["exit_codes"]
        doc.update(
            status=info["steps"].get(step),
            # workflow.log has one code per step from step 1 on; none for step 0
            exit_code=codes[step - 1] if 1 <= step <= len(codes) else None,
            workflow_steps=info["steps"],
            workflow_exit_codes=codes,
            problems=[_trim(p) for p in result["problems"]],
        )
    except Exception as e:
        doc["scan_error"] = f"{type(e).__name__}: {e}"
    return _write_json(doc, os.path.join(outbox, "relval", scan_file_name(where, "relval")))


def main(argv: list[str]) -> int:
    """By hand:
    ib_test_log_problems.py <unpacked dir> <zip path> [<out path>]   unit tests / addOn
    ib_test_log_problems.py step <RelVal step log>                   one step, into the outbox"""
    if len(argv) == 3 and argv[1] == "step":
        print(write_relval_step_scan(argv[2]) or "skipped (DBG, or the outbox is not open)")
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
    print(
        f"wrote {out} in {time.time() - started:.1f} s"
        if out
        else "skipped (the outbox is not open)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
