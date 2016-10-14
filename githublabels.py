LABEL_COLORS = {
  "hold" : "eb6420",
  "pending":  "fbca04",
  "approved": "009800",
  "rejected": "e11d21",
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
  "new-feature" : "0000ff",
  "backport" : "0000ff",
  "urgent"   : "cc317c",
  "process-complete" : "006b75",
  "hold": LABEL_COLORS["hold"],
}

COMPARISON_LABELS = {
  "comparison-notrun" : "bfe5bf",
  "comparison-available" : LABEL_TYPES["approved"],
  "comparison-pending" : LABEL_TYPES["pending"],
}

MATERIAL_BUDGET_LABELS = {
  "material-budget-available" : LABEL_TYPES["approved"],
  "material-budget-comparison" : LABEL_TYPES["approved"],
  "material-budget-rejected" : LABEL_COLORS["rejected"],
}

CMSSW_BUILD_LABELS = {
  "build-aborted" : "5319e7",
  "build-in-progress" : LABEL_TYPES["pending"],
  "build-pending-approval" : "fef2c0",
  "build-successful" : LABEL_TYPES["approved"],
  "release-notes-requested" : "bfe5bf",
  "release-announced" : LABEL_TYPES["approved"],
  "toolconf-building" : "fef2c0",
  "uploading-builds" : "86A086",
}

