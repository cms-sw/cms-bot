LABEL_TYPES = {
  "pending":  "fbca04",
  "approved": "009800",
  "rejected": "e11d21",
  "hold": "eb6420",
}

COMMON_LABELS = {
  "test-started": LABEL_TYPES["hold"],
  "fully-signed": LABEL_TYPES["approved"],
  "pending-signatures": LABEL_TYPES["hold"],
}

COMPARISON_LABELS = {
  "comparison-available" : LABEL_TYPES["approved"],
  "comparison-pending" : LABEL_TYPES["pending"],
}

