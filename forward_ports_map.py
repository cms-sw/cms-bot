#CMS GIT Repositories automatic forward port map
#FORMAT:
#GIT_REPO_FWPORTS[repo][source-branch]=[destination-branch[:strategy]]
#e.g
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"]=["CMSSW_7_6_ROOT64_X", "CMSSW_8_0_X:ours"]

GIT_REPO_FWPORTS = {"cmsdist" : {},"cmssw" : {}}
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_6_2_X/stable"]=["IB/CMSSW_6_2_X/devel-gcc472"]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_0_X/stable"]=["IB/CMSSW_7_1_X/stable"]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_3_X/stable"]=["IB/CMSSW_7_3_X/gcc491","IB/CMSSW_7_3_X/root6","IB/CMSSW_7_3_X/next","IB/CMSSW_7_3_X/debug"]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_4_X/stable"]=["IB/CMSSW_7_4_X/gcc481","IB/CMSSW_7_4_X/next","IB/CMSSW_7_4_X/root6","IB/CMSSW_7_4_X/geant10","IB/CMSSW_7_4_X/debug","IB/CMSSW_7_4_X/root5"]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_5_X/stable"]=["IB/CMSSW_7_5_X/gcc481","IB/CMSSW_7_5_X/next","IB/CMSSW_7_5_X/root5"]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_6_X/stable"]=["IB/CMSSW_7_6_X/next","IB/CMSSW_7_6_X/gcc493"]

GIT_REPO_FWPORTS["cmssw"]["CMSSW_6_2_X"]=["CMSSW_6_2_X_SLHC"]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_6_2_X_SLHC"]=["CMSSW_6_2_SLHCDEV_X"]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_4_X"]=["CMSSW_7_4_DEVEL_X","CMSSW_7_4_THREADED_X","CMSSW_7_4_ROOT6_X","CMSSW_7_4_GEANT10_X","CMSSW_7_4_CLANG_X","CMSSW_7_4_ROOT5_X"]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_5_X"]=["CMSSW_7_5_ROOT5_X","CMSSW_7_5_ROOT64_X"]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"]=["CMSSW_7_6_ROOT64_X"]

#Something like following should be automatically added for each new release cycle
#i.e first forward port the previous production branch in to new release cycle production branch
#and then forward port new production branch to its devel branches
#GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_7_6_X/stable"].append("IB/CMSSW_8_0_X/stable")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"].append("IB/CMSSW_8_0_X/next")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/stable"].append("IB/CMSSW_8_0_X/gcc530")

GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/gcc530"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_0_X/gcc530"].append("IB/CMSSW_8_0_X/gcc530G4")

#GIT_REPO_FWPORTS["cmssw"]["CMSSW_7_6_X"].append("CMSSW_8_0_X")
GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_0_X"]=[]
#disable CMSSW_8_0_X -> CMSSW_8_0_ROOT64_X as ROOT64 80X IBs are disbaled.
#GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_0_X"].append("CMSSW_8_0_ROOT64_X")

#Automatically added for CMSSW new branch CMSSW_8_1_X
GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"]=[]
GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_ROOT64_X")
GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_ROOT6_X")
GIT_REPO_FWPORTS["cmssw"]["CMSSW_8_1_X"].append("CMSSW_8_1_DEVEL_X")

#Automatically added for CMSDIST new branch IB/CMSSW_8_1_X/stable
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"]=[]
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/gcc530next")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/gcc600")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X/root6")
GIT_REPO_FWPORTS["cmsdist"]["IB/CMSSW_8_1_X/gcc530"].append("IB/CMSSW_8_1_X//gcc530_ppc64le")

