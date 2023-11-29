try:
    from categories import get_dpg_pog
except:

    def get_dpg_pog():
        return []


LABEL_COLORS = {
    "hold": "ff8000",
    "pending": "fbca04",
    "approved": "2cbe4e",
    "rejected": "e11d21",
    "info": "0000ff",
    "doc": "257fdb",
}

LABEL_TYPES = {
    "pending": LABEL_COLORS["pending"],
    "approved": LABEL_COLORS["approved"],
    "rejected": LABEL_COLORS["rejected"],
}

# TYPE_COMMANDS[LABEL_NAME]=[LABEL_COLOR,
#                           REGEXP_TO_MATCH_CCOMMENT",
#                           TYPE
#                                type: only apply the last comment
#                                mtype: accomulate all comments]
TYPE_COMMANDS = {
    "bug-fix": ["b8860b", "bug(-fix|fix|)", "type"],
    "new-feature": [LABEL_COLORS["info"], "(new-|)(feature|idea)", "type"],
    "root": [LABEL_COLORS["info"], "root", "mtype"],
    "documentation": [LABEL_COLORS["doc"], "doc(umentation|)", "mtype"],
    "performance-improvements": [
        "5b9ee3",
        "performance|improvements|performance-improvements",
        "mtype",
    ],
}

for lab in get_dpg_pog():
    if lab in TYPE_COMMANDS:
        continue
    TYPE_COMMANDS[lab] = [LABEL_COLORS["doc"], lab, "mtype"]

TEST_IGNORE_REASON = ["manual-override", "ib-failure", "external-failure"]

COMMON_LABELS = {
    "tests-started": LABEL_COLORS["hold"],
    "fully-signed": LABEL_COLORS["approved"],
    "pending-signatures": LABEL_COLORS["hold"],
    "pending-assignment": LABEL_COLORS["hold"],
    "new-package-pending": LABEL_COLORS["rejected"],
    "backport": LABEL_COLORS["info"],
    "backport-ok": LABEL_COLORS["approved"],
    "urgent": "cc317c",
    "process-complete": LABEL_COLORS["approved"],
    "hold": LABEL_COLORS["hold"],
    "compilation-warnings": LABEL_COLORS["hold"],
    "requires-external": LABEL_COLORS["info"],
}

for lab in TYPE_COMMANDS:
    COMMON_LABELS[lab] = TYPE_COMMANDS[lab][0]

for reason in TEST_IGNORE_REASON:
    COMMON_LABELS["tests-" + reason] = LABEL_COLORS["info"]

COMPARISON_LABELS = {
    "comparison-notrun": "bfe5bf",
    "comparison-available": LABEL_TYPES["approved"],
    "comparison-pending": LABEL_TYPES["pending"],
}

CMSSW_BUILD_LABELS = {
    "build-aborted": LABEL_COLORS["rejected"],
    "build-in-progress": LABEL_COLORS["hold"],
    "build-pending-approval": LABEL_TYPES["pending"],
    "build-successful": LABEL_TYPES["approved"],
    "release-notes-requested": LABEL_TYPES["approved"],
    "release-announced": LABEL_TYPES["approved"],
    "toolconf-building": LABEL_COLORS["hold"],
    "uploading-builds": LABEL_COLORS["hold"],
    "release-build-request": LABEL_COLORS["approved"],
}
