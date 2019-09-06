#CMS GIT Repositories automatic forward port map
#FORMAT:
#GIT_REPO_FWPORTS[repo][source-branch]=[destination-branch[:strategy]]
#e.g
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"]=["CMSSW_7_6_ROOT64_X", "CMSSW_8_0_X:ours"]
from releases import CMSSW_DEVEL_BRANCH

GIT_REPO_FWPORTS = {"cmsdist" : {},"cmssw" : {}}

#Forward port master branch to latest dev branch
#Master branch is always forward ported to one branch.
GIT_REPO_FWPORTS["cmssw"]["master"]=[CMSSW_DEVEL_BRANCH]

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_6_2_X/stable"]=["IB/CMSSW_6_2_X/devel-gcc472"]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_0_X/stable"]=["IB/CMSSW_7_1_X/stable"]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_3_X/stable"]=["IB/CMSSW_7_3_X/gcc491","IB/CMSSW_7_3_X/root6","IB/CMSSW_7_3_X/next","IB/CMSSW_7_3_X/debug"]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_4_X/stable"]=["IB/CMSSW_7_4_X/gcc481","IB/CMSSW_7_4_X/next","IB/CMSSW_7_4_X/root6","IB/CMSSW_7_4_X/geant10","IB/CMSSW_7_4_X/debug","IB/CMSSW_7_4_X/root5"]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_5_X/stable"]=["IB/CMSSW_7_5_X/gcc481","IB/CMSSW_7_5_X/next","IB/CMSSW_7_5_X/root5"]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_6_X/stable"]=["IB/CMSSW_7_6_X/next","IB/CMSSW_7_6_X/gcc493"]

#GIT_REPO_FWPORTS["cmssw"]["CMSSW_6_2_X"]=["CMSSW_6_2_X_SLHC"]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_6_2_X_SLHC"]=["CMSSW_6_2_SLHCDEV_X"]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_4_X"]=["CMSSW_7_4_DEVEL_X","CMSSW_7_4_THREADED_X","CMSSW_7_4_ROOT6_X","CMSSW_7_4_GEANT10_X","CMSSW_7_4_CLANG_X","CMSSW_7_4_ROOT5_X"]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_5_X"]=["CMSSW_7_5_ROOT5_X","CMSSW_7_5_ROOT64_X"]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"]=["CMSSW_7_6_ROOT64_X"]

#Something like following should be automatically added for each new release cycle
#i.e first forward port the previous production branch in to new release cycle production branch
#and then forward port new production branch to its devel branches
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_6_X/stable"].append("IB/CMSSW_8_0_X/stable")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"].append("IB/CMSSW_8_0_X/next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"].append("IB/CMSSW_8_0_X/gcc530")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/gcc530"].append("IB/CMSSW_8_0_X/gcc530G4")

#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"].append("CMSSW_8_0_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_0_X"]=[]
#disable CMSSW_8_0_X -> CMSSW_8_0_ROOT64_X as ROOT64 80X IBs are disbaled.
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_0_X"].append("CMSSW_8_0_ROOT64_X")

#Automatically added for CMSSW new branch CMSSW_8_1_X
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_ROOT64_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_DEVEL_X")

#Automatically added for CMSDIST new branch IB/CMSSW_8_1_X/stable
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/gcc530next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/gcc600")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/root6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/gcc530_ppc64le")

#Added explicitly by Shahzad MUZAFFAR
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_0_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_0_X"].append("CMSSW_9_0_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_0_X"].append("CMSSW_9_0_DEVEL_X")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc530"].append("IB/CMSSW_9_0_X/gcc620")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc530"].append("IB/CMSSW_9_0_X/root6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc620"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc620"].append("IB/CMSSW_9_0_X/gcc620next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc620"].append("IB/CMSSW_9_0_X/gcc630")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_0_X/gcc620"].append("IB/CMSSW_9_0_X/gcc700")

#Added explicitly by Shahzad MUZAFFAR
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_1_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_1_X"].append("CMSSW_9_1_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_1_X"].append("CMSSW_9_1_DEVEL_X")

GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc530"].append("IB/CMSSW_9_1_X/root6")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc530"].append("IB/CMSSW_9_1_X/gcc630")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc630"].append("IB/CMSSW_9_1_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc630"].append("IB/CMSSW_9_1_X/gcc700")

#Added explicitly by Shahzad MUZAFFAR
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_2_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_2_X"].append("CMSSW_9_2_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_2_X"].append("CMSSW_9_2_DEVEL_X")

GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc530"].append("IB/CMSSW_9_2_X/root6")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc530"].append("IB/CMSSW_9_2_X/gcc630")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc630"].append("IB/CMSSW_9_2_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc630"].append("IB/CMSSW_9_2_X/gcc700")

#Added explicitly by Shahzad MUZAFFAR
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_3_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_3_X"].append("CMSSW_9_3_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_3_X"].append("CMSSW_9_3_DEVEL_X")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc530"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc530"].append("IB/CMSSW_9_3_X/root6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc530"].append("IB/CMSSW_9_3_X/gcc630")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc630"].append("IB/CMSSW_9_3_X/rootgcc6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc630"].append("IB/CMSSW_9_3_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_3_X/gcc630"].append("IB/CMSSW_9_3_X/gcc700")

#Added explicitly by Shahzad MUZAFFAR
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"]=[]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_MAOD_X")
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_AN_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_DEVEL_X")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_4_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_4_X/gcc630"].append("IB/CMSSW_9_4_X/rootgcc6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_4_X/gcc630"].append("IB/CMSSW_9_4_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_4_X/gcc630"].append("IB/CMSSW_9_4_X/gcc700")

#Added explicitly by Shahzad MUZAFFAR
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_0_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_0_X"].append("CMSSW_10_0_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_0_X"].append("CMSSW_10_0_DEVEL_X")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_0_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_0_X/gcc630"].append("IB/CMSSW_10_0_X/root612")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_0_X/gcc630"].append("IB/CMSSW_10_0_X/rootgcc6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_0_X/gcc630"].append("IB/CMSSW_10_0_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_0_X/gcc630"].append("IB/CMSSW_10_0_X/gcc700")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_1_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_1_X"].append("CMSSW_10_1_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_1_X"].append("CMSSW_10_1_DEVEL_X")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"].append("IB/CMSSW_10_1_X/root612")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"].append("IB/CMSSW_10_1_X/rootgcc6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"].append("IB/CMSSW_10_1_X/gcc630next")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"].append("IB/CMSSW_10_1_X/gcc700")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_2_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_2_X"].append("CMSSW_10_2_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_2_X"].append("CMSSW_10_2_DEVEL_X")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc700"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc630"].append("IB/CMSSW_10_2_X/root612")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc630"].append("IB/CMSSW_10_2_X/rootgcc6")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc630"].append("IB/CMSSW_10_2_X/gcc630next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc630"].append("IB/CMSSW_10_2_X/gcc700")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_2_X/gcc700"].append("IB/CMSSW_10_2_X/gcc810")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_3_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_3_X"].append("CMSSW_10_3_ROOT6_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_3_X"].append("CMSSW_10_3_DEVEL_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_3_X"].append("CMSSW_10_3_GEANT4_X")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"].append("IB/CMSSW_10_3_X/rootnext")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"].append("IB/CMSSW_10_3_X/rootmaster")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"].append("IB/CMSSW_10_3_X/gcc700next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"].append("IB/CMSSW_10_3_X/gcc820")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_3_X/gcc700"].append("IB/CMSSW_10_3_X/geant4")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_4_X"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"].append("IB/CMSSW_10_4_X/rootnext")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"].append("IB/CMSSW_10_4_X/rootmaster")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"].append("IB/CMSSW_10_4_X/gcc700next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"].append("IB/CMSSW_10_4_X/gcc820")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_4_X/gcc700"].append("IB/CMSSW_10_4_X/geant4")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_5_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_5_X"].append("CMSSW_10_5_DEVEL_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_5_X"].append("CMSSW_10_5_CXXMODULE_X")

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/gcc700next")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/rootnext")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/rootmaster")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/gcc820")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/geant4")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/cxxmodule")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_5_X/gcc700"].append("IB/CMSSW_10_5_X/geant104")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_6_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_6_X"].append("CMSSW_10_6_DEVEL_X")
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_10_6_X"].append("CMSSW_10_6_ROOT614_X")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/rootnext")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/rootmaster")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/gcc700next")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/gcc820")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/geant4")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/cxxmodule")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/geant104")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/gcc9")

#Automatically added
GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_0_X"]=[]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_0_X"].append("CMSSW_11_0_DEVEL_X")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/rootnext")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/rootmaster")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/gcc700next")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/devel")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/gcc820")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/geant4")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/cxxmodule")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/geant104")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/gcc700"].append("IB/CMSSW_11_0_X/gcc9")

#Added explicitly by Zygimantas Matonis
GIT_REPO_FWPORTS["cms-sw.github.io"] = {
    "code": ["master"]
}
