#Default development branch
# Changes from master branch will be merge in to it
# Any PR open against this will be automatically closed by cms-bot (Pr should be made for master branch)
# For new release cycle just change this and make sure to add its milestone and production branches
CMSSW_DEVEL_BRANCH = "CMSSW_9_1_X"

#Map of cmssw branch to milestone
RELEASE_BRANCH_MILESTONE = {
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

#PR created for these BRANCHES will be closed by cms-bot
RELEASE_BRANCH_CLOSED = [
  "CMSSW_4_1_X",
  "CMSSW_4_2_X",
  "CMSSW_4_4_X",
  "CMSSW_6_1_X",
  "CMSSW_6_1_X_SLHC",
  "CMSSW_6_2_X",
  "CMSSW_7_0_X",
]

#All these releases require ORP signicatures
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

SPECIAL_RELEASE_MANAGERS = ["davidlange6"]

RELEASE_MANAGERS={}
######################################################################
# Automatically added by cms-bot for CMSSW_8_1_X release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_8_1_X"]=59
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_DEVEL_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_8_1_ROOT6_X")

######################################################################
# Automatically added by cms-bot for CMSSW_8_0_0_patchX release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["CMSSW_8_0_0_patchX"]=60

#CMSSW_9_0_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_0_X"]=64
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_0_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_0_ROOT6_X")

#CMSSW_9_1_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_1_X"]=65
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_1_DEVEL_X")

#CMSSW_9_2_X release cycle
RELEASE_BRANCH_MILESTONE["CMSSW_9_2_X"]=66
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_ROOT6_X")
RELEASE_BRANCH_PRODUCTION.append("CMSSW_9_2_DEVEL_X")

######################################################################
# Added by smuzafar for Development release cycle
######################################################################
RELEASE_BRANCH_MILESTONE["master"]=RELEASE_BRANCH_MILESTONE[CMSSW_DEVEL_BRANCH]
RELEASE_BRANCH_PRODUCTION.append("master")

###############################################
#All release should be added before this line
###############################################
USERS_TO_TRIGGER_HOOKS = set(SPECIAL_RELEASE_MANAGERS + [ m for rel in RELEASE_MANAGERS for m in rel ])

