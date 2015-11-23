LABEL_TYPES = {
  "pending":  "fbca04",
  "approved": "009800",
  "rejected": "e11d21",
}

COMMON_LABELS = {
  "test-started": LABEL_TYPES["hold"],
  "fully-signed": LABEL_TYPES["approved"],
  "pending-signatures": LABEL_TYPES["hold"],
  "pending-assignment": LABEL_TYPES["hold"],
  "new-package-pending" : LABEL_TYPES["rejected"],
  "bug-fix" : "b8860b",
  "new-feature" : "0000ff",
  "process-complete" : "006b75",
  "hold": "eb6420",
}

COMPARISON_LABELS = {
  "comparison-available" : LABEL_TYPES["approved"],
  "comparison-pending" : LABEL_TYPES["pending"],
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

