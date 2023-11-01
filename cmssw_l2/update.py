#!/usr/bin/env python
from sys import argv, exit
from json import load, dump

try:
    from categories import CMSSW_L2
except Exception as e:
    print("Python import error:", e)
    exit(0)
try:
    from categories import CMSSW_L1
except:
    CMSSW_L1 = {}

l2_file = argv[1]
ctime = int(int(argv[2]) / 86400) * 86400
data = {}
with open(l2_file) as ref:
    data = load(ref)

for u in CMSSW_L1:
    if u not in CMSSW_L2:
        CMSSW_L2[u] = ["orp"]
    else:
        CMSSW_L2[u].append("orp")

data_chg = False
for u in CMSSW_L2:
    if u not in data:
        data[u] = [{"start_date": ctime, "category": CMSSW_L2[u]}]
        data_chg = True
    elif set(CMSSW_L2[u]) != set(data[u][-1]["category"]):
        if "end_date" not in data[u][-1]:
            data_chg = True
            if data[u][-1]["start_date"] == ctime:
                data[u].pop()
                if not data[u]:
                    del data[u]
            else:
                data[u][-1]["end_date"] = ctime
        if CMSSW_L2[u]:
            data_chg = True
            if u not in data:
                data[u] = [{"start_date": ctime, "category": CMSSW_L2[u]}]
            elif (data[u][-1]["end_date"] == ctime) and (
                set(CMSSW_L2[u]) == set(data[u][-1]["category"])
            ):
                del data[u][-1]["end_date"]
            else:
                data[u].append({"start_date": ctime, "category": CMSSW_L2[u]})
    elif "end_date" in data[u][-1]:
        data[u].append({"start_date": ctime, "category": CMSSW_L2[u]})
        data_chg = True

for u in data:
    if (u not in CMSSW_L2) and ("end_date" not in data[u][-1]):
        data[u][-1]["end_date"] = ctime
        data_chg = True

for u in CMSSW_L2:
    if (u in data) and ("end_date" in data[u][-1]):
        del data[u][-1]["end_date"]
        data_chg = True

if data_chg:
    print("  Updated L2")
    with open(l2_file, "w") as ref:
        dump(data, ref, sort_keys=True, indent=2)
