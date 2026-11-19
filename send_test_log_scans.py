#!/usr/bin/env python3
"""Send the IB test-log scan files from cmssdt9-02 to the chatbot VM.

cms-bot's ib-build-logs and process-relval-logs jobs (Jenkins node `cmssdt` =
cmsbuild@cmssdt9-02) write, next to each test-log zip,

    /data/sdt/buildlogs/<arch>/www/<day>/<queue>/<IB tag>/[gpu/<card>/|other/<name>/]
        unitTestLogs-scan.json.gz | addOnTests-scan.json.gz | pyRelValMatrixLogs-scan.json.gz

This script (its own Jenkins job on the same node, e.g. every 15 min) POSTs each
new or changed one to <url>/api/test-logs/ingest and leaves a marker next to it:

    <scan file>.sent     "<sha256> <answer> <time>"

A file is sent again when its content changed since (a RelVal scan is rewritten
when a late job is merged), never twice otherwise. --resend-days N sends every
file of the last N days again (after the VM was down or rebuilt; the VM answers
"unchanged" for what it already has). The markers go when cms-bot reuses the
weekday folder, like the zips.

Rules: standard library only, Python 3.8+; reads only *-scan.json.gz; never
touches cms-bot's files; never prints the token. Exit 0 = everything sent or
nothing to do, 1 = some files failed or were rejected (retried / reported next
run), 2 = the VM refused the token or is off (nothing sent).

    send_test_log_scans.py --url http://cmssdt-chatbot.cern.ch:8001 [--token-file F] [--dry-run]   (else $TEST_LOGS_INGEST_TOKEN)
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = "/data/sdt/buildlogs"
SCAN_NAMES = (
    "unitTestLogs-scan.json.gz",
    "addOnTests-scan.json.gz",
    "pyRelValMatrixLogs-scan.json.gz",
)
MARK = ".sent"
TOKEN_ENV = "TEST_LOGS_INGEST_TOKEN"
RETRIES = (5, 20)  # seconds to wait before the 2nd and 3rd try of one file
GIVE_UP_AFTER = 5  # files failing in a row: the VM is unreachable, stop this run


class StopRun(Exception):
    pass


def find_scans(root: str) -> list[str]:
    """Every scan file in the build folders, oldest first. Only globs the few
    known levels (a RelVal folder has ~1000 workflow dirs; never walked)."""
    found = []
    for name in SCAN_NAMES:
        for pattern in (
            "*/www/*/*/CMSSW_*/" + name,
            "*/www/*/*/CMSSW_*/gpu/*/" + name,
            "*/www/*/*/CMSSW_*/other/*/" + name,
        ):
            found.extend(
                p
                for p in glob.glob(os.path.join(root, pattern))
                if not os.path.relpath(p, root).startswith("filtered/")
            )
    return sorted(set(found), key=lambda p: (os.path.getmtime(p), p))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sent_hash(path: str) -> str:
    try:
        with open(path + MARK) as fh:
            return fh.read().split()[0]
    except (OSError, IndexError):
        return ""


def mark(path: str, digest: str, answer: str) -> None:
    tmp = path + MARK + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(f"{digest} {answer} {dt.datetime.now():%Y-%m-%dT%H:%M:%S}\n")
    os.replace(tmp, path + MARK)


def post(url: str, token: str, body: bytes, timeout: int = 60) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/gzip", "X-Test-Logs-Token": token},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except ValueError:
            detail = {}
        return exc.code, detail


def send_one(url: str, token: str, path: str, digest: str, sleep=time.sleep) -> str:
    """Returns the VM's answer (saved/replaced/unchanged/older) or raises:
    ValueError = rejected (file is wrong, do not retry it), OSError = could not deliver,
    StopRun = token refused / ingest off."""
    with open(path, "rb") as fh:
        body = fh.read()
    last = ""
    for attempt, wait in enumerate((0,) + RETRIES):
        if wait:
            sleep(wait)
        try:
            code, answer = post(url, token, body)
        except (OSError, ValueError) as exc:  # URLError, timeout, connection reset, bad JSON
            last = f"{type(exc).__name__}: {exc}"
            continue
        if code == 200:
            return str(answer.get("status", "ok"))
        if code in (401, 403, 503):
            raise StopRun(f"HTTP {code}: {answer.get('detail', '')}")
        if code in (400, 413, 422):
            raise ValueError(f"HTTP {code}: {answer.get('detail', '')}")
        last = f"HTTP {code}"
    raise OSError(f"not delivered after {len(RETRIES) + 1} tries ({last})")


def run(
    root: str,
    url: str,
    token: str,
    resend_days: float = 0,
    dry_run: bool = False,
    sleep=time.sleep,
    out=print,
) -> int:
    endpoint = url.rstrip("/") + "/api/test-logs/ingest"
    since = time.time() - resend_days * 86400 if resend_days else None
    counts = {"sent": 0, "unchanged": 0, "skipped": 0, "rejected": 0, "failed": 0}
    failing = 0
    for path in find_scans(root):
        rel = os.path.relpath(path, root)
        digest = sha256(path)
        resend = since is not None and os.path.getmtime(path) >= since
        if sent_hash(path) == digest and not resend:
            counts["skipped"] += 1
            continue
        if dry_run:
            out(f"would send {rel}")
            counts["sent"] += 1
            continue
        try:
            answer = send_one(endpoint, token, path, digest, sleep)
        except StopRun as exc:
            out(f"STOP: the VM refused the upload ({exc}); nothing more sent")
            return 2
        except ValueError as exc:
            out(f"REJECTED {rel}: {exc}")
            mark(path, digest, "rejected")  # not retried until the file changes
            counts["rejected"] += 1
            failing = 0
            continue
        except OSError as exc:
            out(f"FAILED {rel}: {exc}")
            counts["failed"] += 1
            failing += 1
            if failing >= GIVE_UP_AFTER:
                out(
                    f"STOP: {failing} files failed in a row, the VM looks unreachable; next run retries"
                )
                break
            continue
        failing = 0
        mark(path, digest, answer)
        counts["unchanged" if answer == "unchanged" else "sent"] += 1
        out(f"{answer:9} {rel}")
    out(
        "summary: "
        + ", ".join(f"{v} {k}" for k, v in counts.items())
        + (" (dry run)" if dry_run else "")
    )
    return 1 if counts["failed"] or counts["rejected"] else 0


def read_token(token_file: str | None) -> str:
    if token_file:
        with open(os.path.expanduser(token_file)) as fh:
            return fh.read().strip()
    return os.environ.get(TOKEN_ENV, "").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", default=ROOT)
    ap.add_argument(
        "--url", default=os.environ.get("TEST_LOGS_INGEST_URL"), help="the VM's API base URL"
    )
    ap.add_argument("--token-file", help=f"file holding the token (else ${TOKEN_ENV})")
    ap.add_argument("--resend-days", type=float, default=0, help="send the last N days again")
    ap.add_argument("--dry-run", action="store_true", help="only list what would be sent")
    args = ap.parse_args(argv)
    token = read_token(args.token_file)
    if not args.dry_run and (not args.url or not token):
        ap.error("--url (or TEST_LOGS_INGEST_URL) and a token are needed")
    return run(args.root, args.url or "", token, args.resend_days, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
