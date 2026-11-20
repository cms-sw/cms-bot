"""Problem extractor for raw IB test-log zips (unit tests, addOn tests, RelVals).

Reads the zips cms-bot leaves on cmssdt9-02 under
/data/sdt/buildlogs/<arch>/www/<day>/<queue>/<IB tag>/[gpu/<type>/|other/<name>/]:

    unitTestLogs.zip        unitTestLogs/<Sub>/<Pkg>/unitTest.log, one per package
    addOnTests.zip          cmsDriver-<test>_step<N>.log, one per addOn step
                            (statuses come from the sibling addOnTests.log)
    pyRelValMatrixLogs.zip  <wf>/step<N>_<name>.log (+ an identical step<N>.log
                            copy), <wf>/workflow.log with the step statuses

and returns the problems found in every log -- including logs of tests the
dashboard reports as PASSED, which is the point: the dashboard only looks at
how a test exits, never at what it printed.

Problem kinds, most to least serious:

    fatal_exception      ----- Begin Fatal Exception ... ----- End Fatal Exception
    sanitizer            ==PID==ERROR: AddressSanitizer|LeakSanitizer|... + stack
    ubsan                <file>:<line>: runtime error: ...
    crash                CMSSW "A fatal system signal has occurred", or a shell
                         "line N: PID Segmentation fault|Aborted|..." report, or
                         that report alone on its line ("Aborted (core dumped)")
    assertion            glibc "Assertion `...' failed"
    uncaught_exception   terminate called after throwing an instance of '...'
    python_traceback     Traceback (most recent call last): ... <Type>: <msg>
    infrastructure_error known infrastructure failure lines (e.g. UCX)
    message_logger       %MSG-e / %MSG-w / %MSG-s / %MSG-f blocks (info and
                         debug are dropped as noise)
    generic_error_line   any other line containing error/exception/failed --
                         stored quietly, never meant for the shifter digest,
                         because almost all of them are table headers and banners

Every problem carries an `origin` -- "cmssw" (CMSSW code: a CMSSW library in
the stack, or a CMSSW exception/message), "infrastructure" (only system tools
or libraries in the stack, or a known infrastructure failure) or
"unclassified" (anything else; shown, never dropped) -- and a `signature`:
the problem text with run-to-run noise (PIDs, addresses, timestamps, numbers,
release paths) stripped, so the same problem can be recognized across tests
and across IBs. MessageLogger messages are grouped by severity + category,
not by their exact text.

`intentional_hint` is set when the log itself says the problem is on purpose
("Intentional ... for testing purposes", "EXPECTED EXCEPTION", "expected
failure occurred"). It is a hint for the person reviewing, nothing more:
many tests throw on purpose without saying so, so nothing is ever marked
expected automatically.

Self-contained, same spirit as clang_parser.py / relval_log_parser.py: no
Neo4j, no network, no shared state. Zip members are streamed line by line and
never extracted to disk, so a multi-GB DBG log never has to fit in memory.
"""

from __future__ import annotations  # runs on Python 3.8+ (cms-bot's nodes), not only 3.10+

import argparse
import bisect
import collections
import hashlib
import io
import json
import os
import re
import zipfile
import zlib
from collections import deque

SCANNER_VERSION = 6  # bump when detection changes, so stored results say what produced them
MAX_BLOCK_LINES = 60  # lines of evidence kept per problem
MAX_LINE_CHARS = 500  # characters kept per evidence line
MAX_FRAMES = 20  # stack frames kept per sanitizer report
MAX_SCAN_CHARS = 4000  # longer lines are only scanned up to this length
MAX_OCCURRENCE_LINES = 5  # line numbers remembered per aggregated problem
HINT_WINDOW = 5  # lines before/after a problem searched for an "intentional" hint

# ---- test boundaries -------------------------------------------------------

UNIT_TEST_START_RE = re.compile(r'^===== Test "(?P<name>[^"]+)" ====')
UNIT_TEST_STATUS_RE = re.compile(r"^---> test (?P<name>\S+) (?P<status>succeeded|had ERRORS)")
UNIT_TEST_END_RE = re.compile(r"^\^\^\^\^ End Test (?P<name>\S+) \^\^\^\^")
ADDON_STATUS_RE = re.compile(
    r"^\[(?P<test>[^\]:]+):(?P<step>\d+)\] .* : (?P<status>[A-Z_]+) - elapsed"
)
RELVAL_STEP_STATUS_RE = re.compile(r"\bStep(?P<step>\d+)-(?P<status>[A-Z_]+)")
RELVAL_EXIT_RE = re.compile(r";\s*exit:\s*(?P<codes>[-\d ]+)")

# ---- problem detectors -----------------------------------------------------

FATAL_BEGIN_RE = re.compile(r"^-{3,} Begin Fatal Exception")
FATAL_END_RE = re.compile(r"^-{3,} End Fatal Exception")
EXCEPTION_CATEGORY_RE = re.compile(r"An exception of category '(?P<cat>[^']+)' occurred")
EXCEPTION_MESSAGE_RE = re.compile(r"^Exception Message:\s*$")
MSG_BEGIN_RE = re.compile(r"^%MSG-(?P<sev>[a-z]) (?P<cat>[^:\s]+):?")
MSG_END_RE = re.compile(r"^%MSG\s*$")
MSG_SEVERITIES = {"w": "warning", "e": "error", "s": "system", "f": "fatal"}  # i/d dropped
SAN_HEADER_RE = re.compile(
    r"^==\d+==\s*ERROR: (?P<tool>AddressSanitizer|LeakSanitizer|MemorySanitizer|ThreadSanitizer): ?(?P<what>.*)$"
)
TSAN_HEADER_RE = re.compile(r"^WARNING: ThreadSanitizer: (?P<what>.*)$")
SAN_SUMMARY_RE = re.compile(r"^SUMMARY: \w+Sanitizer")
SAN_FRAME_RE = re.compile(r"^\s*#\d+ 0x[0-9a-fA-F]+ (?:in (?P<rest>.+)|(?P<bare>\(.+\)))$")
UBSAN_RE = re.compile(r"(?P<loc>\S+:\d+(?::\d+)?): runtime error: (?P<what>.*)$")
SIGNAL_RE = re.compile(r"A fatal system signal has occurred: (?P<what>.+)$")
SHELL_KILL_RE = re.compile(
    r"line \d+:\s+\d+ (?P<what>Segmentation fault|Aborted|Bus error|Killed|Floating point exception|Illegal instruction)"
)
# the shell's report alone on a line (no "line N: PID" prefix), e.g. from a wrapper;
# only when the line holds nothing else, so prose mentioning "aborted" is not a crash
PLAIN_SIGNAL_RE = re.compile(
    r"^(?P<what>Segmentation fault|Bus error|Aborted|Floating point exception|Illegal instruction)"
    r"(?: \(core dumped\))?\s*$"
)
# CMSSW's names for the signals it reports ("A fatal system signal has occurred: <name>")
CMSSW_SIGNAL_NAMES = (
    "segmentation violation",
    "abort signal",
    "bus error",
    "illegal instruction",
    "floating point exception",
    "external termination request",
    "keyboard interrupt",
)


def signal_name(what: str) -> str:
    """The signal name from a "fatal system signal" line. Output of two threads can be
    glued onto it (": index abort signal-916979453", "abort signalabort signal"), which
    made each such crash a signature of its own; the known name is taken out of it."""
    lowered = (what or "").lower()
    for name in CMSSW_SIGNAL_NAMES:
        if name in lowered:
            return name
    words = re.match(r"[A-Za-z][A-Za-z ]*[A-Za-z]", (what or "").strip(" :"))
    return words.group(0) if words else (what or "").strip()


ASSERTION_RE = re.compile(r"Assertion [`'\"](?P<expr>.+)[`'\"] failed")
TERMINATE_RE = re.compile(r"terminate called after throwing an instance of '(?P<type>[^']+)'")
TRACEBACK_RE = re.compile(r"^Traceback \(most recent call last\):")
PY_FRAME_RE = re.compile(r'^\s*File "(?P<file>[^"]+)", line \d+')
INFRA_LINE_PATTERNS = [
    # MPI/UCX transport failure (seen 160x in one ASAN IB's unit tests)
    ("UCX", re.compile(r"osc_ucx_component\.c:\d+\s+Error:")),
]
GENERIC_ERROR_RE = re.compile(
    r"\b(?:error|ERROR|Error|exception|Exception|EXCEPTION|FAILED|Failed|FATAL|Fatal)\b"
)
# Minified JavaScript is web-page content, not a log message: test_StorageFactory_Http
# prints a downloaded page whose code ("throw Error(...)") changes every day.
MINIFIED_CODE_RE = re.compile(r"\bfunction\s*\(")
# The HLT TrigReport summary's column header ("... Passed  Failed  Error Name") names
# columns, it reports nothing: every HLT addOn test prints it, so it looked like a
# "new" generic line in every newly scanned series.
COLUMN_HEADER_RE = re.compile(r"^TrigReport\b.*\bFailed\s+Error\s+Name\s*$")


def _is_minified_code(line: str) -> bool:
    if MINIFIED_CODE_RE.search(line) and line.count(";") >= 3:
        return True
    # a long line with almost no spaces but lots of ";{}" is code, not a message
    return (
        len(line) >= 80 and line.count(" ") < 0.03 * len(line) and sum(map(line.count, ";{}")) >= 4
    )


INTENTIONAL_RE = re.compile(
    r"intentional|expected (?:failure|exception|error)|for testing purposes|EXPECTED EXCEPTION",
    re.IGNORECASE,
)

# ---- origin classification -------------------------------------------------

CMSSW_LOCATION_RE = re.compile(
    r"/cms/cmssw(?:-patch)?/CMSSW_|\$RELEASE|/CMSSW_\d+_\d+[^/\s]*/(?:src|lib|python|bin)/"
)
SYSTEM_LOCATION_RE = re.compile(r"^\(?(?:/usr)?/(?:s?bin|lib64|lib)/")
SANITIZER_FRAME_RE = re.compile(
    r"libsanitizer|/libasan|/liblsan|/libtsan|/libubsan|__interceptor_|___interceptor_"
)

# ---- signature normalization -----------------------------------------------

_NORMALIZERS = [
    # /data/cmsbld/jenkins/... on x86, /pool/condor/dir_<N>/jenkins/... on the aarch64 nodes
    (re.compile(r"(?:/[\w.-]+)*?/jenkins/workspace/[^/\s]+/CMSSW_[^/\s]+"), "$RELEASE"),
    (re.compile(r"/cvmfs/[^\s()]*?/cms/cmssw(?:-patch)?/CMSSW_[^/\s]+"), "$RELEASE"),
    (
        re.compile(
            r"/cvmfs/[^/\s]+/(?:sw/[^/\s]+/)?(?:nweek-\d+/)?[a-z0-9]+_[a-z0-9]+_[a-z0-9]+/"
        ),
        "$SW/",
    ),
    (re.compile(r"\bCMSSW_\d+_\d+_[A-Za-z0-9_]*?X_\d{4}-\d\d-\d\d-\d{4}\b"), "<IB>"),
    (re.compile(r"/pyRelval/[^/\s]+/"), "/pyRelval/<WF>/"),
    # Madgraph runs in one of several worker dirs: .../pyRelval/<WF>/thread0/lheevent/...
    (re.compile(r"(?<=/)thread\d+(?=/)"), "thread<N>"),
    # interleaved output glues a MessageLogger "%MSG" onto the next line: "%MSGsrc/X.h:12:3: runtime error"
    (re.compile(r"%MSG(?=[\w/$])"), ""),
    (re.compile(r"\d{1,2}-[A-Z][a-z]{2}-\d{4} \d\d:\d\d:\d\d(?:\.\d+)? ?[A-Z]{0,5}"), "<TIME>"),
    (
        re.compile(r"[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d\d:\d\d:\d\d [A-Z]{0,5} ?\d{4}"),
        "<TIME>",
    ),
    (re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:[.,]\d+)?(?:Z|[+-]\d\d:?\d\d)?"), "<TIME>"),
    (
        re.compile(r"\b([IWEF])\d{4} \d\d:\d\d:\d\d(?:\.\d+)?"),
        r"\1<TIME>",
    ),  # glog/PyTorch: W1007 00:51:16.268
    (
        re.compile(r"\[[A-Za-z][\w.-]*:\s*\d+(?:\s*:\s*\w+)?\s*\]"),
        "[<HOST>]",
    ),  # MPI/UCX "[b9g40p4801:3720950:0]"
    (re.compile(r"(?<=Values: )[0-9a-fA-F]+\b"), "<HEX>"),  # ROOT R__unzip_header
    (re.compile(r"==\d+=="), ""),
    (
        re.compile(
            r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"
        ),
        "<GUID>",
    ),
    (re.compile(r"0x[0-9a-fA-F]+"), "<HEX>"),
    (re.compile(r"\b[0-9a-f]{12,}\b"), "<HASH>"),
    (re.compile(r"(?<![A-Za-z_\d.])\d+(?:\.\d+)*(?:[eE][-+]?\d+)?"), "<N>"),
]


def normalize_text(text: str) -> str:
    """Strips what changes from run to run, so the same problem compares equal."""
    for pattern, replacement in _NORMALIZERS:
        text = pattern.sub(replacement, text)
    text = _PUNCT_SPACE_RE.sub(
        r"\1", text
    )  # padding varies: "[host:8304 :0]" vs "[host:314154:0]"
    return " ".join(text.split())[:300]


_PUNCT_SPACE_RE = re.compile(r"\s*([:\[\]()=,;])\s*")


def make_signature(kind: str, category: str | None, detail: str) -> str:
    return f"{kind}|{category or ''}|{normalize_text(detail)}"


def fatal_signature_detail(message: str) -> str:
    """The part of a fatal exception message that identifies it. The stored message is
    the first 300 raw characters; a raw cut lands at a different place in each run
    (release paths differ in length), so the partly cut last word is dropped and the
    cut is made again after normalization -- otherwise one exception gets a new
    signature in every build ("At:$RELEASE/src/F" vs "At:$RELEASE")."""
    message = (message or "")[:300]
    if len(message) >= 300:
        message = message.rsplit(None, 1)[0]
    return normalize_text(message)[:200]


def current_signature(problem: dict) -> str:
    """A stored problem's signature recomputed with the current normalization, so
    results scanned by an older SCANNER_VERSION (whose zips are long deleted) still
    compare equal to new ones. Idempotent: normalizing a normalized text changes nothing.
    MessageLogger signatures have no detail, and their category can itself contain "|"
    ("HGCalGeomT3|4"), so they are left as they are."""
    if problem["signature"].startswith("message_logger|"):
        return problem["signature"]
    kind, category, detail = problem["signature"].split("|", 2)
    if kind == "fatal_exception":
        return make_signature(
            kind, category or None, fatal_signature_detail(problem.get("message"))
        )
    if kind == "crash" and SIGNAL_RE.search(problem.get("message") or ""):
        category = signal_name(category)
    return make_signature(kind, category or None, detail)


def signature_id(signature: str) -> str:
    return hashlib.sha1(signature.encode()).hexdigest()[:16]


def _frame_location(frame_text: str) -> str:
    binary = re.search(r"\((?P<path>/[^()+\s]+)\+0x[0-9a-fA-F]+\)", frame_text)
    if binary:
        return binary.group("path")
    source = re.search(r"\s(?P<path>/\S+?:\d+(?::\d+)?)\s*$", frame_text)
    if source:
        return source.group("path")
    return ""


def classify_frames(frames: list[dict]) -> str:
    """cmssw if any frame is CMSSW code; infrastructure if every frame is a
    system binary/library; otherwise unclassified. Sanitizer runtime frames
    (malloc interceptors etc.) are ignored -- they're in every report."""
    real = [f for f in frames if not SANITIZER_FRAME_RE.search(f["func"] + " " + f["location"])]
    if not real:
        return "unclassified"
    if any(CMSSW_LOCATION_RE.search(f["location"]) for f in real):
        return "cmssw"
    if all(f["location"] and SYSTEM_LOCATION_RE.search(f["location"]) for f in real):
        return "infrastructure"
    return "unclassified"


def _first_real_frame(frames: list[dict]) -> dict | None:
    for f in frames:
        if not SANITIZER_FRAME_RE.search(f["func"] + " " + f["location"]):
            return f
    return None


# ---- the line scanner ------------------------------------------------------


class _Block:
    """A multi-line problem being collected while lines stream past."""

    def __init__(self, kind: str, lineno: int, first_line: str, max_lines: int):
        self.kind = kind
        self.start = lineno
        self.end = lineno
        self.lines = [first_line[:MAX_LINE_CHARS]]
        self.max_lines = max_lines
        self.total = 1
        self.meta: dict = {}
        self.before: list[str] = []

    def add(self, lineno: int, line: str) -> None:
        self.end = lineno
        self.total += 1
        if len(self.lines) < MAX_BLOCK_LINES:
            self.lines.append(line[:MAX_LINE_CHARS])

    def feed(self, lineno: int, line: str, stripped: str) -> bool:
        """Returns True once the block is complete. The line that completes
        it is included only when it belongs to the block."""
        raise NotImplementedError

    def too_long(self) -> bool:
        return self.total >= self.max_lines


class _FatalBlock(_Block):
    def __init__(self, lineno, line):
        super().__init__("fatal_exception", lineno, line, max_lines=5000)
        self.meta.update(category=None, message=[], in_message=False)

    def feed(self, lineno, line, stripped):
        self.add(lineno, line)
        if FATAL_END_RE.match(stripped):
            return True
        if self.meta["category"] is None:
            m = EXCEPTION_CATEGORY_RE.search(stripped)
            if m:
                self.meta["category"] = m.group("cat")
        if EXCEPTION_MESSAGE_RE.match(stripped):
            self.meta["in_message"] = True
        elif self.meta["in_message"] and stripped and len(self.meta["message"]) < 3:
            self.meta["message"].append(stripped)
        return self.too_long()

    def to_issue(self):
        cat = self.meta["category"]
        message = " ".join(self.meta["message"])
        return dict(
            kind="fatal_exception",
            category=cat,
            origin="cmssw",
            message=message[:300],
            summary=f"Fatal exception '{cat}': {message[:150]}",
            signature=make_signature("fatal_exception", cat, fatal_signature_detail(message)),
        )


class _MessageBlock(_Block):
    def __init__(self, lineno, line, severity, category):
        super().__init__("message_logger", lineno, line, max_lines=200)
        self.meta.update(severity=severity, category=category, body=[])

    def feed(self, lineno, line, stripped):
        if MSG_BEGIN_RE.match(stripped):  # unterminated: the next message starts
            return True
        self.add(lineno, line)
        if MSG_END_RE.match(stripped):
            return True
        if stripped and len(self.meta["body"]) < 2:
            self.meta["body"].append(stripped)
        return self.too_long()

    def to_issue(self):
        sev, cat = self.meta["severity"], self.meta["category"]
        message = " ".join(self.meta["body"])
        return dict(
            kind="message_logger",
            category=cat,
            severity=sev,
            origin="cmssw",
            message=message[:300],
            summary=f"%MSG {sev} {cat}: {message[:150]}",
            signature=make_signature("message_logger", f"{sev}:{cat}", ""),
        )


class _SanitizerBlock(_Block):
    def __init__(self, lineno, line, tool, what):
        super().__init__("sanitizer", lineno, line, max_lines=3000)
        self.meta.update(tool=tool, what=what, frames=[], all_frames=[])

    def feed(self, lineno, line, stripped):
        if (
            SAN_HEADER_RE.match(stripped)
            or TSAN_HEADER_RE.match(stripped)
            or UNIT_TEST_STATUS_RE.match(stripped)
            or UNIT_TEST_START_RE.match(stripped)
        ):
            return True
        self.add(lineno, line)
        m = SAN_FRAME_RE.match(line)
        if m:
            rest = m.group("rest") or m.group("bare") or ""
            location = _frame_location(rest)
            func = (
                rest[: rest.rfind(location) - 1].strip(" (")
                if location and location in rest
                else rest
            )
            frame = dict(func=func[:200], location=location)
            if len(self.meta["all_frames"]) < 500:
                self.meta["all_frames"].append(frame)
            if len(self.meta["frames"]) < MAX_FRAMES:
                self.meta["frames"].append(frame)
        return bool(SAN_SUMMARY_RE.match(stripped)) or self.too_long()

    def to_issue(self):
        tool = self.meta["tool"]
        what = re.sub(r" on (?:unknown )?address.*| of size \d+.*", "", self.meta["what"]).strip()
        frames = self.meta["all_frames"]
        origin = classify_frames(frames)
        top = _first_real_frame(frames)
        where = ""
        if top:
            binary = top["location"].rsplit("/", 1)[-1] if top["location"] else "?"
            func = re.sub(r"\(.*", "", top["func"]).strip()
            where = f"{func} in {binary}"
        return dict(
            kind="sanitizer",
            category=f"{tool}: {what}",
            origin=origin,
            message=where,
            frames=self.meta["frames"],
            summary=f"{tool}: {what}" + (f" [{where}]" if where else ""),
            signature=make_signature("sanitizer", f"{tool}: {what}", where),
        )


class _CountedBlock(_Block):
    """Keeps the next N lines as evidence (crash stacks, uncaught exceptions)."""

    def __init__(self, kind, lineno, line, keep, issue):
        super().__init__(kind, lineno, line, max_lines=keep)
        self.issue = issue

    def feed(self, lineno, line, stripped):
        self.add(lineno, line)
        return self.too_long()

    def to_issue(self):
        return self.issue


class _TracebackBlock(_Block):
    def __init__(self, lineno, line):
        super().__init__("python_traceback", lineno, line, max_lines=500)
        self.meta.update(files=[], last=None)

    def feed(self, lineno, line, stripped):
        self.add(lineno, line)
        if line.startswith((" ", "\t")):
            m = PY_FRAME_RE.match(line)
            if m:
                self.meta["files"].append(m.group("file"))
            return self.too_long()
        self.meta["last"] = stripped
        return True

    def to_issue(self):
        last = self.meta["last"] or ""
        exc_type = last.split(":", 1)[0] if ":" in last else last[:80]
        files = self.meta["files"]
        origin = "cmssw" if any(CMSSW_LOCATION_RE.search(f) for f in files) else "unclassified"
        where = normalize_text(files[-1]) if files else ""
        return dict(
            kind="python_traceback",
            category=exc_type,
            origin=origin,
            message=last[:300],
            summary=f"Python {last[:150]}",
            signature=make_signature("python_traceback", exc_type, f"{last[:120]} @ {where}"),
        )


_SINGLE_LINE_PREFILTER = re.compile(
    r"fatal system signal|Segmentation fault|Aborted|Bus error|Killed|Floating point exception|Illegal instruction"
    r"|runtime error|Assertion|terminate called|osc_ucx"
)


def _single_line_issue(line: str, stripped: str) -> tuple[dict, int] | None:
    """Problems recognized from one line. Returns (issue, extra evidence lines to keep)."""
    if not _SINGLE_LINE_PREFILTER.search(stripped):
        return None
    m = SIGNAL_RE.search(stripped)
    if m:
        what = signal_name(m.group("what"))
        return (
            dict(
                kind="crash",
                category=what,
                origin="cmssw",
                message=stripped[:300],
                summary=f"cmsRun crash: fatal system signal ({what})",
                signature=make_signature("crash", what, ""),
            ),
            40,
        )
    m = SHELL_KILL_RE.search(stripped) or PLAIN_SIGNAL_RE.match(stripped)
    if m and "Found custom handler" not in stripped:
        what = m.group("what")
        script = re.search(r"(\S+\.(?:sh|py)): line", stripped)
        return (
            dict(
                kind="crash",
                category=what,
                origin="unclassified",
                message=stripped[:300],
                summary=f"Process {what.lower()}"
                + (f" in {script.group(1).rsplit('/', 1)[-1]}" if script else ""),
                signature=make_signature("crash", what, script.group(1) if script else ""),
            ),
            0,
        )
    m = UBSAN_RE.search(stripped)
    if m:
        loc = m.group("loc")
        origin = "cmssw" if CMSSW_LOCATION_RE.search(loc) or "/src/" in loc else "unclassified"
        return (
            dict(
                kind="ubsan",
                category="runtime error",
                origin=origin,
                message=m.group("what")[:300],
                summary=f"UBSan runtime error: {m.group('what')[:150]}",
                signature=make_signature("ubsan", "runtime error", f"{m.group('what')} @ {loc}"),
            ),
            0,
        )
    m = ASSERTION_RE.search(stripped)
    if m:
        origin = "cmssw" if CMSSW_LOCATION_RE.search(stripped) else "unclassified"
        return (
            dict(
                kind="assertion",
                category="assertion",
                origin=origin,
                message=stripped[:300],
                summary=f"Assertion failed: {m.group('expr')[:150]}",
                signature=make_signature("assertion", None, stripped),
            ),
            0,
        )
    m = TERMINATE_RE.search(stripped)
    if m:
        exc_type = m.group("type")
        origin = "cmssw" if exc_type.startswith(("cms::", "edm::")) else "unclassified"
        return (
            dict(
                kind="uncaught_exception",
                category=exc_type,
                origin=origin,
                message=stripped[:300],
                summary=f"Uncaught exception {exc_type} (terminate called)",
                signature=make_signature("uncaught_exception", exc_type, ""),
            ),
            5,
        )
    for name, pattern in INFRA_LINE_PATTERNS:
        if pattern.search(stripped):
            return (
                dict(
                    kind="infrastructure_error",
                    category=name,
                    origin="infrastructure",
                    message=stripped[:300],
                    summary=f"{name} error: {stripped[:150]}",
                    signature=make_signature("infrastructure_error", name, stripped),
                ),
                0,
            )
    return None


def iter_issues(lines):
    """Scans an iterable of log lines and yields one dict per problem
    occurrence (not aggregated), each with kind, category, origin, summary,
    signature, line_start/line_end (1-based), evidence `block` and
    `intentional_hint`. Streams: memory use doesn't grow with the log size.
    Occurrences come out in completion order, a few lines after they end
    (once the "intentional" hint window has passed)."""
    open_blocks: list[_Block] = []
    recent: deque = deque(maxlen=HINT_WINDOW)  # lines before the current one
    pending: list[tuple[dict, int]] = []  # (issue, last line number searched for a hint)

    def finish(block: _Block, truncated: bool = False) -> None:
        issue = block.to_issue()
        issue.update(
            line_start=block.start,
            line_end=block.end,
            block=block.lines,
            truncated=truncated or block.total > len(block.lines),
        )
        _attach_hint(issue, block.before + block.lines)
        pending.append((issue, block.end + HINT_WINDOW))

    lineno = 0
    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        scanned = line[:MAX_SCAN_CHARS]
        stripped = scanned.strip()

        if pending:
            if INTENTIONAL_RE.search(stripped):
                for issue, _ in pending:
                    if not issue.get("intentional_hint"):
                        issue["intentional_hint"] = stripped[:200]
            if pending[0][1] <= lineno or len(pending) > 1:
                keep = []
                for issue, until in pending:
                    if until <= lineno:
                        yield issue
                    else:
                        keep.append((issue, until))
                pending = keep

        covered = bool(open_blocks)
        still_open = []
        for block in open_blocks:
            if block.feed(lineno, scanned, stripped):
                finish(block)
            else:
                still_open.append(block)
        open_blocks = still_open

        opened_before = len(open_blocks)
        started = True
        if FATAL_BEGIN_RE.match(stripped):
            open_blocks.append(_FatalBlock(lineno, scanned))
        elif stripped.startswith("%MSG-") and (m := MSG_BEGIN_RE.match(stripped)):
            severity = MSG_SEVERITIES.get(m.group("sev"))
            if severity:
                open_blocks.append(_MessageBlock(lineno, scanned, severity, m.group("cat")))
            else:
                started = False
                covered = True  # info/debug messages are noise, not generic error lines
        elif "Sanitizer" in stripped and (
            m := SAN_HEADER_RE.match(stripped) or TSAN_HEADER_RE.match(stripped)
        ):
            open_blocks.append(
                _SanitizerBlock(
                    lineno,
                    scanned,
                    m.groupdict().get("tool") or "ThreadSanitizer",
                    m.group("what"),
                )
            )
        elif TRACEBACK_RE.match(stripped):
            open_blocks.append(_TracebackBlock(lineno, scanned))
        elif single := _single_line_issue(scanned, stripped):
            issue, keep_lines = single
            if keep_lines:
                open_blocks.append(
                    _CountedBlock(issue["kind"], lineno, scanned, keep_lines + 1, issue)
                )
            else:
                issue.update(
                    line_start=lineno,
                    line_end=lineno,
                    block=[scanned[:MAX_LINE_CHARS]],
                    truncated=False,
                )
                _attach_hint(issue, list(recent) + [stripped])
                pending.append((issue, lineno + HINT_WINDOW))
        else:
            started = False
        for block in open_blocks[opened_before:]:
            block.before = list(recent)

        if (
            not started
            and not covered
            and GENERIC_ERROR_RE.search(stripped)
            and not _is_minified_code(stripped)
            and not COLUMN_HEADER_RE.match(stripped)
        ):
            yield dict(
                kind="generic_error_line",
                category=None,
                origin="unclassified",
                message=stripped[:300],
                summary=stripped[:150],
                signature=make_signature("generic_error_line", None, stripped[:200]),
                line_start=lineno,
                line_end=lineno,
                block=[scanned[:MAX_LINE_CHARS]],
                truncated=False,
                intentional_hint=None,
            )
        recent.append(stripped)

    for block in open_blocks:
        finish(block, truncated=True)
    for issue, _ in pending:
        yield issue


def scan_lines(lines) -> list[dict]:
    """iter_issues as a list in log order -- for small inputs and tests."""
    return sorted(iter_issues(lines), key=lambda i: i["line_start"])


def _attach_hint(issue: dict, context_lines) -> None:
    for text in context_lines:
        if INTENTIONAL_RE.search(text):
            issue["intentional_hint"] = text.strip()[:200]
            return
    issue["intentional_hint"] = None


# ---- aggregation -----------------------------------------------------------

# ---- problem details: every module, producer, name and context line --------
# The signature is (kind, category, message) only, so the same message from two
# producers is one problem. These details are kept from every occurrence (not
# just the evidence example), so a search by producer, module label or any name
# finds it, and the chat parses a pasted error with this same function.

CONTEXT_LINE_RE = re.compile(r"^\s*\[\d+\]\s+(?P<what>\S.*)$")
# "Calling method for module TrackstersProducer/'ticlTrackstersCLUE3D'", "Prefetching for module X/'y'"
MODULE_RE = re.compile(r"\bmodule (?:of type )?([A-Za-z_]\w*)/'([^']*)'")
PLUGIN_NAME_RE = re.compile(r"\bplugin name '([A-Za-z_]\w*)'")
SOURCE_TYPE_RE = re.compile(r"\bsource of type ([A-Za-z_]\w*)")
EXECUTABLE_RE = re.compile(r"Running executable \"([^\"]+)\"")
PATH_NAME_RE = re.compile(
    r"\b(?:end)?path '[^']*'", re.I
)  # config-specific, says nothing about the problem
QUOTED_NAME_RE = re.compile(r"['\"]([A-Za-z_][\w:.<>/-]{3,})['\"]")
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][\w]*(?:::[A-Za-z_~][\w]*)*")
_ARCH_RE = re.compile(r"\b(?:el|slc|cc|cs|fc|alma|rhel)\d+_[a-z0-9]+_[a-z]+\d+\b")
_IB_RE = re.compile(r"\bCMSSW_\d+_\d+_[A-Za-z0-9_]*?X_\d{4}-\d\d-\d\d-\d{4}\b")
_NAME_STOPWORDS = {
    "exception",
    "message",
    "category",
    "occurred",
    "while",
    "processing",
    "running",
    "constructing",
    "following",
    "classes",
    "calling",
    "method",
    "module",
    "prefetching",
    "begin",
    "fatal",
    "error",
    "errors",
    "found",
    "unable",
    "cmsrun",
    "cmssw",
    "summary",
    "addresssanitizer",
    "readof",
    "writeof",
}
HEX_LITERAL_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
MAX_NAMES = 40
MAX_CONTEXTS = 20
MAX_DETAIL_OCCURRENCES = (
    200  # occurrences per record whose details are merged (a debug log repeats one line 1M times)
)


def _identifier_like(token: str) -> bool:
    return (
        len(token) >= 5
        and token.lower() not in _NAME_STOPWORDS
        and bool(
            re.search(r"[a-z][A-Z]|[A-Z]{2,}[a-z]", token)
            or re.search(r"\d", token)
            or "_" in token
            or "::" in token
        )
    )


def problem_details(lines, category: str | None = None) -> dict:
    """modules (Type/'label'), producers (module types, cfi plugin names, source
    types), executable, names (every specific name: quoted names, producers,
    labels, C++/Python identifiers -- scope parts too), context_keys
    ("<category>|<producer>", "<category>|exe:<executable>": same producer, any
    message) and contexts (the normalized "[N] ..." lines) of one problem block."""
    text_lines = [l.rstrip("\r\n") for l in lines]
    context = "\n".join(m.group("what") for m in map(CONTEXT_LINE_RE.match, text_lines) if m)
    body = "\n".join(l for l in text_lines if not CONTEXT_LINE_RE.match(l))
    modules = list(dict.fromkeys(f"{t}/'{label}'" for t, label in MODULE_RE.findall(context)))
    producers = list(
        dict.fromkeys(
            [t for t, _ in MODULE_RE.findall(context)]
            + PLUGIN_NAME_RE.findall(context)
            + SOURCE_TYPE_RE.findall(context)
        )
    )
    executables = EXECUTABLE_RE.findall(context)
    names: list[str] = []
    for name in (
        producers
        + [label for _, label in MODULE_RE.findall(context) if len(label) >= 4]
        + QUOTED_NAME_RE.findall(PATH_NAME_RE.sub(" ", MODULE_RE.sub(" ", context + "\n" + body)))
        + executables
    ):
        if name != category:
            names.append(name)
    # memory addresses ("0x50d0005dfb30") change every run; tokenized they became
    # names like "x50d0005dfb30" that a paste then "shared" by chance (found 2026-10-15)
    plain = HEX_LITERAL_RE.sub(
        " ", _ARCH_RE.sub(" ", _IB_RE.sub(" ", PATH_NAME_RE.sub(" ", context + "\n" + body)))
    )
    for token in _IDENTIFIER_RE.findall(plain):
        if not _identifier_like(token) or token == category:
            continue
        names.append(token)
        if "::" in token:
            names.extend(part for part in token.split("::") if _identifier_like(part))
    names = list(dict.fromkeys(names))[:MAX_NAMES]
    keys = [f"{category or ''}|{p}" for p in producers] + [
        f"{category or ''}|exe:{e}" for e in executables
    ]
    contexts = list(
        dict.fromkeys(
            normalize_text(m.group("what")) for m in map(CONTEXT_LINE_RE.match, text_lines) if m
        )
    )
    return dict(
        modules=modules[:MAX_CONTEXTS],
        producers=producers[:MAX_CONTEXTS],
        executable=executables[0] if executables else None,
        names=names,
        context_keys=list(dict.fromkeys(keys))[:MAX_CONTEXTS],
        contexts=contexts[:MAX_CONTEXTS],
    )


DETAIL_FIELDS = (
    ("modules", MAX_CONTEXTS),
    ("producers", MAX_CONTEXTS),
    ("names", MAX_NAMES),
    ("context_keys", MAX_CONTEXTS),
    ("contexts", MAX_CONTEXTS),
)


def merge_details(target: dict, details: dict) -> None:
    """Adds one occurrence's details to a record's (order kept, capped)."""
    for field, cap in DETAIL_FIELDS:
        merged = target.setdefault(field, [])
        for value in details.get(field) or []:
            if len(merged) >= cap:
                break
            if value not in merged:
                merged.append(value)


MAX_GENERIC_SIGNATURES = 1000  # per owner; a multi-GB debug log must not blow up memory


def aggregate(issues, owner: dict | None = None, owner_of=None) -> dict:
    """Groups occurrences by signature: one record per (owner, signature) with
    a count, the first occurrence as evidence, the first few line numbers, and
    the modules/producers/names/context lines of every occurrence (up to
    MAX_DETAIL_OCCURRENCES; generic error lines have none -- the line is all there is).
    Pass a fixed `owner` dict, or `owner_of(issue) -> dict` when owners differ
    by position in the log (unit tests). Beyond MAX_GENERIC_SIGNATURES
    distinct generic lines per owner, the rest are only counted, in one
    "(other generic error lines)" record."""
    grouped: dict = {}
    generic_per_owner: collections.Counter = collections.Counter()
    for issue in issues:
        who = owner_of(issue) if owner_of else (owner or {})
        who_key = tuple(sorted(who.items()))
        signature = issue["signature"]
        key = (who_key, signature)
        record = grouped.get(key)
        if record is None and issue["kind"] == "generic_error_line":
            if generic_per_owner[who_key] >= MAX_GENERIC_SIGNATURES:
                signature = make_signature(
                    "generic_error_line", None, "(other generic error lines)"
                )
                key = (who_key, signature)
                record = grouped.get(key)
                if record is None:
                    issue = dict(issue, signature=signature, summary="(other generic error lines)")
            else:
                generic_per_owner[who_key] += 1
        if record is None:
            record = dict(
                issue, **who, count=0, occurrence_lines=[], signature_id=signature_id(signature)
            )
            grouped[key] = record
        record["count"] += 1
        if record["count"] <= MAX_DETAIL_OCCURRENCES and issue["kind"] != "generic_error_line":
            merge_details(record, problem_details(issue.get("block") or [], issue.get("category")))
        if len(record["occurrence_lines"]) < MAX_OCCURRENCE_LINES:
            record["occurrence_lines"].append(issue["line_start"])
        if not record.get("intentional_hint") and issue.get("intentional_hint"):
            record["intentional_hint"] = issue["intentional_hint"]
    return grouped


MAX_LINE_BYTES = (
    64 * 1024
)  # longer lines are cut while reading: one test prints a 2 GB line of zeros
_LONE_CR_RE = re.compile(r"(?<=\r)(?!\n)")


def _bounded_lines(stream, limit: int = MAX_LINE_BYTES):
    """Text lines from a binary stream, never holding more than `limit` bytes
    of one line (the rest of an over-long line is skipped). Lines end at \\n,
    \\r\\n or a lone \\r, like TextIOWrapper(newline="")."""
    while True:
        line = stream.readline(limit)
        if not line:
            return
        if len(line) == limit and not line.endswith(b"\n"):
            while True:
                rest = stream.readline(limit)
                if not rest or rest.endswith(b"\n"):
                    break
            line += b"\n"
        text = line.decode("utf-8", "replace")
        if "\r" in text:
            yield from (part for part in _LONE_CR_RE.split(text) if part)
        else:
            yield text


def _member_lines(zf: zipfile.ZipFile, info: zipfile.ZipInfo):
    with zf.open(info) as raw:
        yield from _bounded_lines(io.BufferedReader(raw, buffer_size=1 << 20))


class _ZipMemberLines:
    """Re-iterable view of one zip member: each iteration streams it again."""

    def __init__(self, zf: zipfile.ZipFile, info: zipfile.ZipInfo):
        self.zf, self.info = zf, info

    def __iter__(self):
        return _member_lines(self.zf, self.info)


def _file_lines(path: str):
    with open(path, "rb", buffering=1 << 20) as raw:
        yield from _bounded_lines(raw)


class _FileLines:
    """Re-iterable view of one file on disk (an unpacked zip member)."""

    def __init__(self, path: str):
        self.path = path

    def __iter__(self):
        return _file_lines(self.path)


def _zip_members(zf: zipfile.ZipFile):
    """(member name, re-iterable lines) for every file in a zip, in zip order."""
    for info in zf.infolist():
        if not info.is_dir():
            yield info.filename, _ZipMemberLines(zf, info)


def _dir_members(root: str):
    """(member name, re-iterable lines) for every file under an unpacked zip
    folder. Names are relative to `root` with "/" separators, i.e. exactly the
    names the files had inside the zip, so results match a zip scan."""
    for dirpath, dirnames, files in os.walk(root):
        dirnames.sort()
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            yield os.path.relpath(path, root).replace(os.sep, "/"), _FileLines(path)


# ---- unit tests ------------------------------------------------------------


def unit_test_spans(lines) -> list[dict]:
    """Real tests are the names that get a '---> test NAME ...' status line.

    Some tests run several commands and print a nested
    '===== Test "<command>" ====' header for each one -- those are not tests
    (cms-bot's own summary calls them a "test mismatch") and stay inside the
    enclosing test. One pass over `lines`, keeping only the marker lines.
    """
    statuses: dict[str, str] = {}
    starts: list[tuple[int, str]] = []
    ends: dict[str, list[int]] = collections.defaultdict(list)
    total = 0
    for total, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("====="):
            m = UNIT_TEST_START_RE.match(stripped)
            if m:
                starts.append((total, m.group("name")))
        elif stripped.startswith("--->"):
            m = UNIT_TEST_STATUS_RE.match(stripped)
            if m:
                statuses[m.group("name")] = (
                    "passed" if m.group("status") == "succeeded" else "failed"
                )
        elif stripped.startswith("^^^^"):
            m = UNIT_TEST_END_RE.match(stripped)
            if m:
                ends[m.group("name")].append(total)
    real = [(lineno, name) for lineno, name in starts if name in statuses]
    tests = []
    for idx, (lineno, name) in enumerate(real):
        next_start = real[idx + 1][0] if idx + 1 < len(real) else total + 1
        end = next((e for e in ends.get(name, []) if lineno <= e < next_start), next_start - 1)
        tests.append(dict(test=name, status=statuses[name], line_start=lineno, line_end=end))
    return tests


def scan_unit_test_log(lines, package: str, member: str = "") -> tuple[list[dict], list[dict]]:
    """Returns (tests, aggregated problems) for one package's unitTest.log.
    `lines` must be re-iterable (a list, or _ZipMemberLines): it is read twice,
    once for the test boundaries and once for the problems."""
    tests = unit_test_spans(lines)
    for t in tests:
        t.update(package=package, member=member)
    starts = [t["line_start"] for t in tests]

    def owner_of(issue):
        idx = bisect.bisect_right(starts, issue["line_start"]) - 1
        test = tests[idx] if idx >= 0 and issue["line_start"] <= tests[idx]["line_end"] else None
        return dict(
            package=package,
            test=test["test"] if test else None,
            test_status=test["status"] if test else None,
            member=member,
        )

    return tests, list(aggregate(iter_issues(lines), owner_of=owner_of).values())


def _scan_unit_test_members(members) -> dict:
    tests, problems = [], []
    for member, lines in members:
        if not member.endswith("/unitTest.log"):
            continue
        package = "/".join(member.split("/")[1:-1])
        t, p = scan_unit_test_log(lines, package, member)
        tests.extend(t)
        problems.extend(p)
    return dict(kind="unit", tests=tests, problems=problems)


def scan_unit_test_zip(path: str) -> dict:
    with zipfile.ZipFile(path) as zf:
        return _scan_unit_test_members(_zip_members(zf))


def scan_unit_test_dir(root: str) -> dict:
    """Same as scan_unit_test_zip, for the zip already unpacked into `root`."""
    return _scan_unit_test_members(_dir_members(root))


# ---- addOn tests -----------------------------------------------------------


def parse_addon_statuses(addon_log_text: str) -> dict[str, dict]:
    """addOnTests.log lines like '[hlt_mc_GRun:2] cmsRun ... : PASSED - elapsed ...'
    -> {'cmsDriver-hlt_mc_GRun_step2.log': {test, step, status}}."""
    statuses = {}
    for line in addon_log_text.splitlines():
        m = ADDON_STATUS_RE.match(line.strip())
        if m:
            test, step = m.group("test"), int(m.group("step"))
            statuses[f"cmsDriver-{test}_step{step}.log"] = dict(
                test=test,
                step=step,
                status="passed" if m.group("status") == "PASSED" else "failed",
                raw_status=m.group("status"),
            )
    return statuses


def _scan_addon_members(members, addon_log_text: str) -> dict:
    statuses = parse_addon_statuses(addon_log_text)
    tests, problems = [], []
    for member, lines in members:
        name = member.rsplit("/", 1)[-1]
        if not name.endswith(".log"):
            continue
        status = statuses.get(name)
        if status is None:
            m = re.match(r"cmsDriver-(?P<test>.+)_step(?P<step>\d+)\.log$", name)
            status = dict(
                test=m.group("test") if m else name,
                step=int(m.group("step")) if m else None,
                status=None,
                raw_status=None,
            )
        tests.append(dict(status, member=member))
        owner = dict(
            test=status["test"], step=status["step"], test_status=status["status"], member=member
        )
        problems.extend(aggregate(iter_issues(iter(lines)), owner).values())
    return dict(kind="addon", tests=tests, problems=problems)


def scan_addon_zip(path: str, addon_log_text: str) -> dict:
    with zipfile.ZipFile(path) as zf:
        return _scan_addon_members(_zip_members(zf), addon_log_text)


def scan_addon_dir(root: str, addon_log_text: str) -> dict:
    """Same as scan_addon_zip, for the zip already unpacked into `root`."""
    return _scan_addon_members(_dir_members(root), addon_log_text)


# ---- RelVals ---------------------------------------------------------------


def parse_relval_workflow_log(text: str) -> dict:
    """'140.051_RunMuonEG2022C Step0-PASSED Step1-FAILED ...; exit: 0 256' ->
    {steps: {1: 'PASSED', 2: 'FAILED'}, exit_codes: [0, 256]}. workflow.log
    counts steps from 0; log files count from 1, so Step0 is step1."""
    steps = {int(s) + 1: status for s, status in RELVAL_STEP_STATUS_RE.findall(text)}
    exit_match = RELVAL_EXIT_RE.search(text)
    exit_codes = [int(c) for c in exit_match.group("codes").split()] if exit_match else []
    return dict(steps=steps, exit_codes=exit_codes)


def _relval_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    return {"PASSED": "passed", "NOTRUN": "not_run"}.get(raw, "failed")


class _RelvalZipFile:
    """One file of a RelVal zip, as _scan_relval_members needs it."""

    def __init__(self, zf: zipfile.ZipFile, info: zipfile.ZipInfo):
        self.zf, self.info, self.name, self.size = zf, info, info.filename, info.file_size
        self.lines = _ZipMemberLines(zf, info)

    def read(self) -> bytes:
        return self.zf.read(self.info)

    def crc(self) -> int:
        return self.info.CRC


class _RelvalDiskFile:
    """One file of an unpacked RelVal folder. crc() is the zip's CRC-32 of the
    content, computed only when asked (two logs of a workflow with equal size)."""

    def __init__(self, path: str, name: str):
        self.path, self.name, self.size = path, name, os.path.getsize(path)
        self.lines = _FileLines(path)
        self._crc = None

    def read(self) -> bytes:
        with open(self.path, "rb") as fh:
            return fh.read()

    def crc(self) -> int:
        if self._crc is None:
            crc = 0
            with open(self.path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    crc = zlib.crc32(chunk, crc)
            self._crc = crc
        return self._crc


def _scan_relval_members(files) -> dict:
    """`files`: every <workflow>/<file> of a RelVal zip or unpacked folder.
    Files at any other depth (top-level markers, sub-folders) are ignored."""
    workflows, problems = [], []
    members = collections.defaultdict(list)
    for f in files:
        parts = f.name.split("/")
        if len(parts) == 2 and parts[1]:
            members[parts[0]].append(f)
    for wf in sorted(members):
        files_of_wf = members[wf]
        status_file = next((f for f in files_of_wf if f.name.endswith("/workflow.log")), None)
        parsed = (
            parse_relval_workflow_log(status_file.read().decode("utf-8", "replace"))
            if status_file
            else dict(steps={}, exit_codes=[])
        )
        workflows.append(
            dict(
                workflow=wf,
                steps=parsed["steps"],
                exit_codes=parsed["exit_codes"],
                status=(
                    None
                    if not parsed["steps"]
                    else (
                        "passed"
                        if all(s == "PASSED" for s in parsed["steps"].values())
                        else "failed"
                    )
                ),
            )
        )
        # step<N>.log is a byte-identical copy of the named step log (or of the
        # das/lumi log); read each distinct content once, preferring the named file.
        kept_by_size = collections.defaultdict(list)
        logs = [
            f
            for f in files_of_wf
            if f.name.endswith(".log")
            and f.name.rsplit("/", 1)[1] not in ("workflow.log", "time.log")
        ]
        logs.sort(
            key=lambda f: (
                re.fullmatch(r"step\d+\.log", f.name.rsplit("/", 1)[1]) is not None,
                f.name,
            )
        )
        for f in logs:
            same_size = kept_by_size[f.size]
            if same_size and any(k.crc() == f.crc() for k in same_size):
                continue
            same_size.append(f)
            name = f.name.rsplit("/", 1)[1]
            step_match = re.match(r"step(\d+)", name)
            step = int(step_match.group(1)) if step_match else None
            raw = parsed["steps"].get(step) if step else None
            owner = dict(
                workflow=wf,
                step=step,
                test_status=_relval_status(raw),
                raw_status=raw,
                member=f.name,
            )
            problems.extend(aggregate(iter_issues(iter(f.lines)), owner).values())
    return dict(kind="relval", workflows=workflows, problems=problems)


def scan_relval_zip(path: str) -> dict:
    with zipfile.ZipFile(path) as zf:
        return _scan_relval_members(
            _RelvalZipFile(zf, info) for info in zf.infolist() if not info.is_dir()
        )


def scan_relval_dir(root: str) -> dict:
    """The same as scan_relval_zip, for the folder cms-bot zips into
    pyRelValMatrixLogs.zip (pyRelValPartialLogs/, scanned before it is zipped)."""
    files = []
    for wf in sorted(os.listdir(root)):
        wf_dir = os.path.join(root, wf)
        if os.path.isdir(wf_dir):
            files.extend(
                _RelvalDiskFile(os.path.join(wf_dir, name), f"{wf}/{name}")
                for name in sorted(os.listdir(wf_dir))
                if os.path.isfile(os.path.join(wf_dir, name))
            )
    return _scan_relval_members(files)


# ---- command line: a read-only report, writes nothing anywhere ------------

SERIOUS_KINDS = (
    "fatal_exception",
    "sanitizer",
    "ubsan",
    "crash",
    "assertion",
    "uncaught_exception",
    "python_traceback",
    "infrastructure_error",
)


def _report(result: dict) -> str:
    problems = result["problems"]
    units = result.get("tests") or result.get("workflows") or []
    out = [
        f"# {result['kind']}: {len(units)} tests/workflows "
        f"({collections.Counter(u.get('status') for u in units)})",
        "",
    ]
    counts = collections.Counter((p["kind"], p["origin"], p.get("test_status")) for p in problems)
    occurrences = collections.Counter()
    for p in problems:
        occurrences[(p["kind"], p["origin"], p.get("test_status"))] += p["count"]
    out.append("| kind | origin | test status | records | occurrences |")
    out.append("|---|---|---|---|---|")
    for key, n in sorted(counts.items(), key=lambda kv: -occurrences[kv[0]]):
        out.append(f"| {key[0]} | {key[1]} | {key[2]} | {n} | {occurrences[key]} |")
    out += ["", "## Serious problems in tests that PASSED", ""]
    serious = collections.defaultdict(list)
    for p in problems:
        if p["kind"] in SERIOUS_KINDS and p.get("test_status") == "passed":
            serious[p["signature"]].append(p)
    for sig, rows in sorted(
        serious.items(), key=lambda kv: (kv[1][0]["origin"] != "cmssw", kv[1][0]["kind"])
    ):
        first = rows[0]
        who = sorted(
            {
                "/".join(
                    str(r.get(k)) for k in ("package", "test", "workflow", "step") if r.get(k)
                )
                for r in rows
            }
        )
        hint = f" -- hint: {first['intentional_hint']}" if first.get("intentional_hint") else ""
        out.append(
            f"- [{first['origin']}] {first['summary'][:140]} x{sum(r['count'] for r in rows)} "
            f"in {len(who)}: {', '.join(who[:4])}{' ...' if len(who) > 4 else ''}{hint}"
        )
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("zip_path")
    parser.add_argument(
        "--addon-log", help="addOnTests.log next to addOnTests.zip (default: same folder)"
    )
    parser.add_argument("--json", help="also write the full result as JSON to this path")
    args = parser.parse_args()
    name = args.zip_path.rsplit("/", 1)[-1]
    if name.startswith("unitTestLogs"):
        result = scan_unit_test_zip(args.zip_path)
    elif name.startswith("addOnTests"):
        log_path = args.addon_log or args.zip_path.rsplit("/", 1)[0] + "/addOnTests.log"
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            result = scan_addon_zip(args.zip_path, fh.read())
    elif name.startswith("pyRelValMatrixLogs"):
        result = scan_relval_zip(args.zip_path)
    else:
        parser.error(f"don't know what kind of zip {name} is")
    print(_report(result))
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=1, default=str)


if __name__ == "__main__":
    main()
