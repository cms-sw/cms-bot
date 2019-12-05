#CMS GIT Repositories automatic forward port map
#FORMAT:
#GIT_REPO_FWPORTS[repo][source-branch]=[destination-branch[:strategy]]
#e.g
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"]=["CMSSW_7_6_ROOT64_X", "CMSSW_8_0_X:ours"]
from releases import CMSSW_DEVEL_BRANCH

GIT_REPO_FWPORTS = {"cmsdist" : {},"cmssw" : {}}

#Added explicitly by Zygimantas Matonis
GIT_REPO_FWPORTS["cms-sw.github.io"] = {
    "code": ["master"]
}

#Forward port master branch to latest dev branch
#Master branch is always forward ported to one branch.
GIT_REPO_FWPORTS["cmssw"]["master"]=[CMSSW_DEVEL_BRANCH]

GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc530"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_1_X/gcc530"].append("IB/CMSSW_9_1_X/gcc630")

GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc530"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_9_2_X/gcc530"].append("IB/CMSSW_9_2_X/gcc630")

#Added explicitly by Shahzad MUZAFFAR
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"]=[]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_MAOD_X")
GIT_REPO_FWPORTS["cmssw"]["CMSSW_9_4_X"].append("CMSSW_9_4_AN_X")

#Automatically added
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_1_X/gcc630"].append("IB/CMSSW_10_1_X/gcc700")

#Automatically added
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_10_6_X/gcc700"].append("IB/CMSSW_10_6_X/gcc820")

#Automatically added
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_0_X"]=[]
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_0_X"].append("CMSSW_11_0_DEVEL_X")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"]=[]
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/rootnext")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/rootmaster")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/devel")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/geant4")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/rootmodule")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/gcc9")
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/py3")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_0_X/master"].append("IB/CMSSW_11_0_X/cc8")

#Automatically added
GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_1_X"]=[]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_11_1_X"].append("CMSSW_11_1_DEVEL_X")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"]=[]

#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/gcc700")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/rootnext")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/rootmaster")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/devel")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/geant4")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/rootmodule")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/gcc9")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/py3")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_11_1_X/master"].append("IB/CMSSW_11_1_X/cc8")
