# Map of cmssw branch to milestone
RELEASE_BRANCH_MILESTONE = {
    "CMSSW_9_2_6_patchX": 70,
    "CMSSW_9_2_3_patchX": 68,
    "CMSSW_9_2_0_patchX": 67,
    "CMSSW_8_0_10_patchX": 63,
    "CMSSW_8_0_8_patchX": 62,
    "CMSSW_7_5_5_patchX": 58,
    "CMSSW_8_0_X": 57,
    "CMSSW_7_6_X": 55,
    "CMSSW_7_5_X": 51,
    "CMSSW_7_4_X": 50,
    "CMSSW_7_3_X": 49,
    "CMSSW_7_0_X": 38,
    "CMSSW_7_1_X": 47,
    "CMSSW_7_2_X": 48,
    "CMSSW_6_2_X": 21,
    "CMSSW_6_2_X_SLHC": 9,
    "CMSSW_5_3_X": 20,
    "CMSSW_4_4_X": 8,
    "CMSSW_4_2_X": 35,
    "CMSSW_4_1_X": 7,
    "CMSSW_6_2_SLHCDEV_X": 52,
    "CMSSW_7_1_4_patchX": 53,
    "CMSSW_7_4_1_patchX": 54,
    "CMSSW_7_4_12_patchX": 56,
}

# PR created for these BRANCHES will be closed by cms-bot
RELEASE_BRANCH_CLOSED = [
    "CMSSW_4_1_X",
    "CMSSW_4_2_X",
    "CMSSW_4_4_X",
    "CMSSW_6_1_X",
    "CMSSW_6_1_X_SLHC",
    "CMSSW_6_2_X",
    "CMSSW_7_0_X",
    "CMSSW_.+_Patatrack_X",
]

# All these releases require ORP signicatures
RELEASE_BRANCH_PRODUCTION = [
    "CMSSW_8_0_X",
    "CMSSW_7_6_X",
    "CMSSW_7_5_X",
    "CMSSW_7_4_X",
    "CMSSW_7_3_X",
    "CMSSW_7_2_X",
    "CMSSW_7_1_X",
    "CMSSW_7_0_X",
    "CMSSW_6_2_X_SLHC",
    "CMSSW_5_3_X",
]

SPECIAL_RELEASE_MANAGERS = []

RELEASE_MANAGERS = {}
RELEASE_MANAGERS["CMSSW_.+_Patatrack_X"] = ["fwyzard"]

######################################################################
# Automatically added by cms-bot for CMSSW_14_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_14_0_X"] = 3
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_0_DEVEL_X")

RELEASE_BRANCH_MILESTONE["CMSSW_14_1_X"] = 4
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_1_DEVEL_X")

RELEASE_BRANCH_MILESTONE["CMSSW_16_0_X"] = 5
RELEASE_BRANCH_PRODUCTION.append("CMSSW_16_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_16_0_FASTPU_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_16_0_RNTUPLE_X")
