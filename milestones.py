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
# Automatically added by cms-bot for CMSSW_8_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_8_1_X"] = 59
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_8_0_0_patchX release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_8_0_0_patchX"] = 60

# CMSSW_9_0_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_0_X"] = 64
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_0_ROOT6_X")

# CMSSW_9_1_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_1_X"] = 65
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_DEVEL_X")

# CMSSW_9_2_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_2_X"] = 66
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_DEVEL_X")

# CMSSW_9_3_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_3_X"] = 69
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_3_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_3_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_3_DEVEL_X")

# CMSSW_9_4_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_4_X"] = 71
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_4_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_4_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_4_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_0_X"] = 72
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_0_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_0_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_1_X"] = 73
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_1_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_1_DEVEL_X")

######################################################################
# Manually added by Shahzad MUZAFFAR for CMSSW_9_4_MAOD_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_9_4_MAOD_X"] = 74
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_4_MAOD_X")

######################################################################
# Manually added by Shahzad MUZAFFAR for CMSSW_9_4_AN_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_9_4_AN_X"] = 75
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_4_AN_X")


######################################################################
# Automatically added by cms-bot for CMSSW_10_2_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_2_X"] = 76
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_2_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_2_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_3_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_3_X"] = 77
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_3_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_3_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_3_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_4_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_4_X"] = 78
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_4_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_4_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_4_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_4_GEANT4_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_5_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_5_X"] = 79
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_5_X")

######################################################################
# Automatically added by cms-bot for CMSSW_10_6_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_10_6_X"] = 80
RELEASE_BRANCH_PRODUCTION.append("CMSSW_10_6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_11_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_11_0_X"] = 81
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_0_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_0_CXXMODULE_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_0_ROOT614_X")

######################################################################
# Automatically added by cms-bot for CMSSW_11_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_11_1_X"] = 82
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_1_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_11_2_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_11_2_X"] = 83
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_2_CLANG_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_2_Patatrack_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_2_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_11_3_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_11_3_X"] = 84
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_3_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_3_CLANG_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_3_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_11_3_Patatrack_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_0_X"] = 85
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_0_Patatrack_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_0_GEANT4_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_0_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_1_X"] = 86
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_1_GEANT4_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_1_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_1_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_2_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_2_X"] = 87
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_2_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_2_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_3_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_3_X"] = 88
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_3_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_3_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_3_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_4_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_4_X"] = 89
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_4_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_4_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_4_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_5_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_5_X"] = 90
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_5_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_5_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_5_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_12_6_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_12_6_X"] = 91
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_6_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_12_6_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_13_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_13_0_X"] = 92
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_0_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_0_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_13_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_13_1_X"] = 93
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_1_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_1_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_13_2_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_13_2_X"] = 94
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_2_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_2_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_13_3_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_13_3_X"] = 95
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_3_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_13_3_DEVEL_X")

######################################################################
# Automatically added by cms-bot for CMSSW_14_0_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_14_0_X"] = 96
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_14_0_DEVEL_X")
