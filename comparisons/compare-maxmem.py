#!/usr/bin/env python3
import sys
import json
from collections import defaultdict


def create_memory_report_dict(filename):
    memory_reports = dict(dict())
    with open(filename, encoding="utf8", errors="ignore") as f:
        step_key = "key"
        for line in f:
            if line.startswith("step"):
                step_key = line.strip()
                memory_reports[step_key] = dict()
                memory_reports[step_key]["step"] = step_key
            else:
                if line.startswith("Memory Report:"):
                    fields = line.split(":")
                    memory_reports[step_key][fields[1].strip()] = int(fields[2].strip())
    return memory_reports


mem_prof_pr_dicts = create_memory_report_dict(sys.argv[1])

mem_prof_base_dicts = create_memory_report_dict(sys.argv[2])

mem_prof_pdiffs_dicts = dict(dict())

for k in mem_prof_pr_dicts.keys():
    mem_prof_pdiffs_dict = dict()
    mem_prof_pr_subdict = mem_prof_pr_dicts[k]
    for j, v in mem_prof_pr_subdict.items():
        if j == "step":
            mem_prof_pdiffs_dict[j] = v
        else:
            mem_prof_pdiffs_dict[j] = (
                100
                * (mem_prof_pr_dicts[k][j] - mem_prof_base_dicts[k][j])
                / mem_prof_base_dicts[k][j]
            )
    mem_prof_pdiffs_dicts[k] = mem_prof_pdiffs_dict

mem_prof = {}

mem_prof["max memory pr"] = mem_prof_pr_dicts
mem_prof["max memory base"] = mem_prof_base_dicts
mem_prof["max memory pdiffs"] = mem_prof_pdiffs_dicts
WARN_THRESHOLD = 1.0
ERROR_THRESHOLD = 10.0
mem_prof["threshold"] = WARN_THRESHOLD
mem_prof["error_threshold"] = ERROR_THRESHOLD
mem_prof["workflow"] = sys.argv[1].split("/")[-2]
sys.stdout.write(json.dumps(mem_prof))
sys.stdout.write("\n")

errs = 0
for k in sorted(mem_prof_pdiffs_dicts.keys()):
    mmu = mem_prof_pdiffs_dicts[k].get("max memory used")
    if mmu:
        if abs(mmu) > ERROR_THRESHOLD:
            errs = errs + 1
            sys.stderr.write(
                "Workflow %s %s max memory used percentage diff %2f%% exceeds error threshold %2f%%"
                % (mem_prof["workflow"], k, abs(mmu), ERROR_THRESHOLD)
            )
            sys.stderr.write("\n")

if errs > 0:
    exit(10)
