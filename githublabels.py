LABEL_COLORS = {
  "hold" : "ff8000",
  "pending":  "fbca04",
  "approved": "2cbe4e",
  "rejected": "e11d21",
  "info": "0000ff",
}

LABEL_TYPES = {
  "pending":  LABEL_COLORS["pending"],
  "approved": LABEL_COLORS["approved"],
  "rejected": LABEL_COLORS["rejected"],
}

COMMON_LABELS = {
  "tests-started": LABEL_COLORS["hold"],
  "fully-signed": LABEL_COLORS["approved"],
  "pending-signatures": LABEL_COLORS["hold"],
  "pending-assignment": LABEL_COLORS["hold"],
  "new-package-pending" : LABEL_COLORS["rejected"],
  "bug-fix" : "b8860b",
  "new-feature" : LABEL_COLORS["info"],
  "backport" : LABEL_COLORS["info"],
  "backport-ok" : LABEL_COLORS["approved"],
  "urgent"   : "cc317c",
  "process-complete" : LABEL_COLORS["approved"],
  "hold": LABEL_COLORS["hold"],
  "compilation-warnings": LABEL_COLORS["hold"],
  "requires-external" : LABEL_COLORS["info"],
}

COMPARISON_LABELS = {
  "comparison-notrun" : "bfe5bf",
  "comparison-available" : LABEL_TYPES["approved"],
  "comparison-pending" : LABEL_TYPES["pending"],
}

CMSSW_BUILD_LABELS = {
  "build-aborted" : LABEL_COLORS["rejected"],
  "build-in-progress" : LABEL_COLORS["hold"],
  "build-pending-approval" : LABEL_TYPES["pending"],
  "build-successful" : LABEL_TYPES["approved"],
  "release-notes-requested" : LABEL_TYPES["approved"],
  "release-announced" : LABEL_TYPES["approved"],
  "toolconf-building" : LABEL_COLORS["hold"],
  "uploading-builds" : LABEL_COLORS["hold"],
  "release-build-request" : LABEL_COLORS["approved"],
}

