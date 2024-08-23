#!/usr/bin/env python3
from cmsutils import get_config_map_properties

specs = get_config_map_properties({"DISABLED": "1"})
data = {}
days = range(7)
hours = (0, 11, 23)
for day in days:
    data[day] = {}
    for hour in hours[1:]:
        data[day][hour] = []
data[0] = {0: [], 23: []}
data[6] = {11: []}
dev_rel = []
for spec in specs:
    rel = "_".join(spec["CMSDIST_TAG"].split("/")[1].split("_")[:3])
    if "BUILD_PATCH_RELEASE" in spec:
        dev_rel.append(rel)
    sel_days = days[:]
    sel_hours = hours[:]
    if "BUILD_DAY" in spec:
        sel_days = []
        for day in spec["BUILD_DAY"].split(","):
            try:
                day = int(day.strip())
                if not day in data:
                    continue
                sel_days.append(day)
            except:
                pass
    if "BUILD_HOUR" in spec:
        sel_hours = []
        for hour in spec["BUILD_HOUR"].split(","):
            try:
                hour = int(hour.strip())
                if not hour in hours:
                    continue
                sel_hours.append(hour)
            except:
                pass
    for day in data.keys():
        if not day in sel_days:
            continue
        for hour in data[day].keys():
            if not hour in sel_hours:
                continue
            if (rel in dev_rel) or ((day == 0) and (hour == 0)):
                data[day][hour].append(spec)
            elif (not 0 in sel_days) or (not not 0 in sel_hours):
                data[day][hour].append(spec)

print("Day\tHour\tx86_64\tppc64le\taarch64")
for day in data.keys():
    for hour in data[day].keys():
        str = "%s\t%s\t" % (day, hour)
        cnt = {"amd64": 0, "ppc64le": 0, "aarch64": 0}
        for spec in data[day][hour]:
            arch = spec["SCRAM_ARCH"].split("_")[1]
            cnt[arch] += 1
        str += "%s\t%s\t%s" % (cnt["amd64"], cnt["ppc64le"], cnt["aarch64"])
        print(str)
