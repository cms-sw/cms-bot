#!/usr/bin/env python3
"""Send the IB test-log scan files from cmssdt9-02 to the chatbot VM, then delete them.

cms-bot's jobs on Jenkins node `cmssdt` (cmsbuild@cmssdt9-02) write one file per
unit/addOn zip (es_ibs_log.py) and per RelVal step (parseLog) into the outbox:

    /data/sdt/chatbot-outbox/{unit,addon,relval}/*.json.gz

This script (its own Jenkins job on the same node) sends everything that is waiting:

  1. moves a batch of files to <outbox>/sending/<kind>/ -- if cms-bot writes a file
     again meanwhile, the new one lands in the outbox and is not touched;
  2. POSTs the batch (a tar) to <url>/api/test-logs/batch;
  3. deletes a file only if the VM confirmed it with the file's own sha256 (saved, or
     refused but kept there for the chatbot people to look at);
  4. repeats until the outbox is empty (or --max-minutes is over), and sends which jobs of
     the recent RelVal builds reported back (the done.<i>of<N> files in pyRelValPartialLogs),
     so the VM knows when a build is complete.

Nothing stays on this machine and nobody has to clean up: the outbox is normally empty.
A file that was not confirmed is sent again next run; after KEEP_DAYS (the VM was down that
long) it is deleted. Left-over .tmp files are deleted after a day.

On/off: the first run creates the outbox, and every run renews its modification time;
cms-bot scans only while that is less than a day old. So running this job switches the
scan on, and if the job stops, the scan stops by itself. `rm -rf` of the outbox removes
everything there ever was.

Rules: standard library only, Python 3.8+; writes only inside the outbox; never
prints the token. Exit 0 = everything sent, nothing to do, or the VM is not reachable
for a short time (retried); 1 = files are waiting for more than an hour, or the VM refused
some; 2 = the VM refused the token or the upload is off (nothing sent, nothing deleted).

    send_test_log_scans.py --url http://cmssdt-chatbot.cern.ch:8001 [--token-file F] [--dry-run]   (else $TEST_LOGS_INGEST_TOKEN)
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import time
import urllib.error
import urllib.request

OUTBOX = "/data/sdt/chatbot-outbox"
BUILDLOGS = "/data/sdt/buildlogs"
KINDS = ("unit", "addon", "relval")  # in this order: a few big answers first, then many steps
BATCH_FILES = 500
BATCH_BYTES = 16 * 1024 * 1024
TOKEN_ENV = "TEST_LOGS_INGEST_TOKEN"
RETRIES = (5, 20)  # seconds to wait before the 2nd and 3rd try of one batch
OLD_FILE_HOURS = 1  # a file waiting longer than this makes the job unstable
KEEP_DAYS = 3  # a file waiting longer than this is deleted
TMP_DAYS = 1  # a .tmp file older than this was left by a killed job
PROGRESS_DAYS = 3  # look at the done.* files of builds touched in the last days
PROGRESS_MEMBER = "progress.json"
PROGRESS_RE = re.compile(
    r"^(?P<arch>[^/]+)/www/[^/]+/[^/]+/(?P<tag>CMSSW_[^/]+)/(?:(?P<variant>(?:gpu|other)/[^/]+)/)?"
    r"pyRelValPartialLogs(?P<closed>\.tmp)?$"
)
DONE_RE = re.compile(r"^done\.")
TOTAL_RE = re.compile(r"^done\.\d+of(\d+)$")


class StopRun(Exception):
    """The VM does not take uploads now (token, switched off, not there yet)."""


class BadBatch(Exception):
    """The VM does not accept this request as a whole."""


def waiting(folder: str) -> list[str]:
    """Finished files of one folder, oldest first (.tmp = still being written)."""
    found = []
    for path in glob.glob(os.path.join(glob.escape(folder), "*.json.gz")):
        try:
            found.append((os.path.getmtime(path), path))
        except OSError:
            pass  # rewritten or gone meanwhile
    return [path for _, path in sorted(found)]


def batches(outbox: str, tried: set[str]):
    """Batches until nothing is waiting (except what was tried in this run): per kind first what an earlier run left in
    sending/, then new files, moved there just before they are sent. A folder is listed
    once per pass, not once per batch (after a day without the VM: > 100000 files)."""
    while True:
        found = False
        for kind in KINDS:
            sending = os.path.join(outbox, "sending", kind)
            os.makedirs(sending, exist_ok=True)
            for folder in (sending, os.path.join(outbox, kind)):
                for batch in chunks([p for p in waiting(folder) if p not in tried]):
                    if folder != sending:
                        batch = [p for p in (claim(path, sending) for path in batch) if p]
                    if batch:
                        found = True
                        yield batch
        if not found:
            return


def chunks(files: list[str]):
    batch, size = [], 0
    for path in files:
        try:
            one = os.path.getsize(path)
        except OSError:
            continue
        if batch and (len(batch) >= BATCH_FILES or size + one > BATCH_BYTES):
            yield batch
            batch, size = [], 0
        batch.append(path)
        size += one
    if batch:
        yield batch


def claim(path: str, sending: str) -> str | None:
    target = os.path.join(sending, os.path.basename(path))
    try:
        os.rename(path, target)
    except FileNotFoundError:
        return None
    return target


def name_of(path: str) -> str:
    """relval/relval__....json.gz -- how a file is called in the batch and the answer."""
    return "/".join(path.split(os.sep)[-2:])


def make_tar(contents: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, data in contents.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def post(url: str, token: str, body: bytes, timeout: int = 120) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-tar", "X-Test-Logs-Token": token},
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


def deliver(url: str, token: str, body: bytes, sleep=time.sleep) -> dict:
    """The VM's answer {"saved": {name: sha256}, "rejected": {name: reason}}.
    StopRun = do not go on, BadBatch = this request is wrong, OSError = not delivered."""
    last = ""
    for wait in (0,) + RETRIES:
        if wait:
            sleep(wait)
        try:
            code, answer = post(url, token, body)
        except (OSError, ValueError) as exc:  # URLError, timeout, connection reset, bad JSON
            last = f"{type(exc).__name__}: {exc}"
            continue
        detail = answer.get("detail", "") if isinstance(answer, dict) else ""
        if code == 200 and isinstance(answer, dict):
            return answer
        if code in (401, 403, 404, 503):
            raise StopRun(f"HTTP {code}: {detail}")
        if code in (400, 413, 422):
            raise BadBatch(f"HTTP {code}: {detail}")
        last = f"HTTP {code}"
    raise OSError(f"not delivered after {len(RETRIES) + 1} tries ({last})")


def send_batch(
    url: str, token: str, batch: list[str], counts: dict, tried: set[str], sleep, out
) -> None:
    contents = {}
    for path in batch:
        with open(path, "rb") as fh:
            contents[name_of(path)] = fh.read()
    try:
        answer = deliver(url, token, make_tar(contents), sleep)
    except BadBatch as exc:
        if len(batch) == 1:
            out(f"REFUSED {name_of(batch[0])}: {exc} (not kept on the VM; deleted)")
            os.remove(batch[0])
            counts["refused"] += 1
            return
        half = len(batch) // 2  # one bad file must not hold up the others
        for part in (batch[:half], batch[half:]):
            send_batch(url, token, part, counts, tried, sleep, out)
        return
    saved, kept = answer.get("saved") or {}, answer.get("kept") or {}
    refused = answer.get("rejected") or {}
    for path in batch:
        name = name_of(path)
        digest = hashlib.sha256(contents[name]).hexdigest()
        if saved.get(name) == digest:
            os.remove(path)
            counts["sent"] += 1
        elif name in refused:
            counts["refused"] += 1
            if kept.get(name) == digest:
                os.remove(path)
                out(f"REFUSED {name}: {refused[name]} (kept on the VM)")
            else:
                tried.add(path)
                out(f"REFUSED {name}: {refused[name]} (the VM has no room to keep it; waits)")
        else:
            tried.add(path)
            counts["unconfirmed"] += 1


def relval_progress(root: str, now: float | None = None) -> dict[str, dict]:
    """{"<arch>/<tag>/<variant or _>": {jobs: [...], total, closed}} for every RelVal
    build touched in the last days, counted like process-relval-logs: every done.* file
    is one job. closed = cms-bot finished the folder (renamed to .tmp): no more jobs."""
    since = (now or time.time()) - PROGRESS_DAYS * 86400
    found: dict[str, dict] = {}
    for below in ("", "gpu/*/", "other/*/"):
        pattern = f"*/www/*/*/CMSSW_*/{below}pyRelValPartialLogs*"
        for folder in glob.glob(os.path.join(glob.escape(root), pattern)):
            m = PROGRESS_RE.match(os.path.relpath(folder, root).replace(os.sep, "/"))
            try:
                if not m or "_DBG_X_" in m.group("tag") or os.path.getmtime(folder) < since:
                    continue
                jobs = {n for n in os.listdir(folder) if DONE_RE.match(n)}
            except OSError:
                continue  # renamed or removed meanwhile
            key = "/".join((m.group("arch"), m.group("tag"), m.group("variant") or "_"))
            entry = found.setdefault(key, dict(jobs=[], total=None, closed=False))
            entry["jobs"] = sorted(jobs | set(entry["jobs"]))
            totals = [t.group(1) for t in map(TOTAL_RE.match, entry["jobs"]) if t]
            entry["total"] = int(totals[-1]) if totals else None
            entry["closed"] = entry["closed"] or bool(m.group("closed"))
    return {key: entry for key, entry in found.items() if entry["jobs"]}


def send_progress(root: str, url: str, token: str, sleep) -> None:
    """All recent builds, every time: the VM ignores what it already knows."""
    now = relval_progress(root)
    if not now:
        return
    data = json.dumps(now, sort_keys=True).encode()
    answer = deliver(url, token, make_tar({PROGRESS_MEMBER: data}), sleep)
    if (answer.get("saved") or {}).get(PROGRESS_MEMBER) != hashlib.sha256(data).hexdigest():
        raise OSError("progress not confirmed")


def folders(outbox: str) -> list[str]:
    return [
        os.path.join(outbox, folder)
        for kind in KINDS
        for folder in (kind, os.path.join("sending", kind))
    ]


def remove_old(outbox: str, out) -> None:
    """Nothing stays here for good: files nobody could take for KEEP_DAYS, .tmp files of a
    killed job, and the sending/ folders when they are empty."""
    now = time.time()
    for days, pattern in ((KEEP_DAYS, "*.json.gz"), (TMP_DAYS, "*.tmp")):
        count = 0
        for folder in folders(outbox):
            for path in glob.glob(os.path.join(glob.escape(folder), pattern)):
                try:
                    if now - os.path.getmtime(path) > days * 86400:
                        os.remove(path)
                        count += 1
                except FileNotFoundError:
                    pass
        if count:
            out(f"deleted {count} {pattern} files older than {days} days")
    sending = os.path.join(outbox, "sending")
    for folder in [os.path.join(sending, kind) for kind in KINDS] + [sending]:
        try:
            os.rmdir(folder)
        except OSError:
            pass  # not empty, or not there


def oldest_hours(outbox: str) -> float:
    """Age of the oldest file that is still here, in hours."""
    ages = [
        time.time() - os.path.getmtime(path)
        for folder in folders(outbox)
        for path in waiting(folder)[:1]
    ]
    return max(ages, default=0) / 3600


def run(
    outbox: str,
    root: str,
    url: str,
    token: str,
    dry_run: bool = False,
    max_minutes: float = 25,
    sleep=time.sleep,
    out=print,
) -> int:
    if dry_run:
        for folder in folders(outbox):
            for path in waiting(folder):
                out(f"would send {name_of(path)}")
        return 0
    os.makedirs(outbox, exist_ok=True)
    os.utime(outbox)  # "the sender is alive": cms-bot scans only while this is recent
    endpoint = url.rstrip("/") + "/api/test-logs/batch"
    counts = {"sent": 0, "refused": 0, "unconfirmed": 0}
    tried: set[str] = set()
    until = time.time() + max_minutes * 60
    code = 0
    try:
        for batch in batches(outbox, tried):
            send_batch(endpoint, token, batch, counts, tried, sleep, out)
            if counts["unconfirmed"]:
                out("STOP: the VM did not confirm every file; they are sent again next run")
                break
            if time.time() > until:
                out(f"stopping after {max_minutes:g} minutes; the next run continues")
                break
        send_progress(root, endpoint, token, sleep)
    except StopRun as exc:
        out(f"STOP: the VM refused the upload ({exc}); nothing more sent, nothing deleted")
        code = 2
    except OSError as exc:
        out(f"NOT SENT: {exc}; next run tries again")
    remove_old(outbox, out)
    age = oldest_hours(outbox)
    if age > OLD_FILE_HOURS:
        out(f"WARNING: files are waiting for {age:.1f} hours")
    out("summary: " + ", ".join(f"{v} {k}" for k, v in counts.items()))
    return code or (1 if counts["refused"] or age > OLD_FILE_HOURS else 0)


def read_token(token_file: str | None) -> str:
    if token_file:
        with open(os.path.expanduser(token_file)) as fh:
            return fh.read().strip()
    return os.environ.get(TOKEN_ENV, "").strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--outbox", default=os.environ.get("CHATBOT_OUTBOX", OUTBOX))
    ap.add_argument("--buildlogs", default=BUILDLOGS, help="where the done.* files are")
    ap.add_argument(
        "--url", default=os.environ.get("TEST_LOGS_INGEST_URL"), help="the VM's API base URL"
    )
    ap.add_argument("--token-file", help=f"file holding the token (else ${TOKEN_ENV})")
    ap.add_argument("--max-minutes", type=float, default=25, help="stop taking new batches then")
    ap.add_argument("--dry-run", action="store_true", help="only list what would be sent")
    args = ap.parse_args(argv)
    token = read_token(args.token_file)
    if not args.dry_run and (not args.url or not token):
        ap.error("--url (or TEST_LOGS_INGEST_URL) and a token are needed")
    return run(args.outbox, args.buildlogs, args.url or "", token, args.dry_run, args.max_minutes)


if __name__ == "__main__":
    sys.exit(main())
