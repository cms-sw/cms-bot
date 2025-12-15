#!/usr/bin/env python3
import os
import sys
import json
from collections import defaultdict

import maxmem_threshold


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
mem_prof_diffs_dicts = dict(dict())

for k in mem_prof_pr_dicts.keys():
    mem_prof_pdiffs_dict = dict()
    mem_prof_diffs_dict = dict()
    mem_prof_pr_subdict = mem_prof_pr_dicts[k]
    for j, v in mem_prof_pr_subdict.items():
        if j == "step":
            mem_prof_pdiffs_dict[j] = v
            mem_prof_diffs_dict[j] = v
        else:
            mem_prof_pdiffs_dict[j] = (
                100
                * (mem_prof_pr_dicts[k][j] - mem_prof_base_dicts[k][j])
                / mem_prof_base_dicts[k][j]
            )
            mem_prof_diffs_dict[j] = mem_prof_pr_dicts[k][j] - mem_prof_base_dicts[k][j]
    mem_prof_pdiffs_dicts[k] = mem_prof_pdiffs_dict
    mem_prof_diffs_dicts[k] = mem_prof_diffs_dict

mem_prof = {}

mem_prof["max memory pr"] = mem_prof_pr_dicts
mem_prof["max memory base"] = mem_prof_base_dicts
mem_prof["max memory pdiffs"] = mem_prof_pdiffs_dicts
mem_prof["max memory diffs"] = mem_prof_diffs_dicts
mem_prof["threshold"] = maxmem_threshold.WARN_THRESHOLD
mem_prof["error_threshold"] = maxmem_threshold.ERROR_THRESHOLD
mem_prof["workflow"] = sys.argv[1].split("/")[-2]
sys.stdout.write(json.dumps(mem_prof))
sys.stdout.write("\n")

errs = 0
for k in sorted(mem_prof_diffs_dicts.keys()):
    mmu = mem_prof_diffs_dicts[k].get("max memory used")
    if mmu:
        mmus = mmu / (1024 * 1024)
        if mmus > maxmem_threshold.WARN_THRESHOLD or mmus < -1 * maxmem_threshold.WARN_THRESHOLD:
            sys.stderr.write(
                "Warning: Workflow %s %s max memory diff %.1f exceeds +/- %.1f MiB\n"
                % (mem_prof["workflow"], k, mmus, maxmem_threshold.WARN_THRESHOLD)
            )
        if mmus > maxmem_threshold.ERROR_THRESHOLD or mmus < -1 * maxmem_threshold.ERROR_THRESHOLD:
            errs = errs + 1
            sys.stderr.write(
                "Error: Workflow %s %s max memory diff %.1f exceeds +/- %.1f MiB\n"
                % (mem_prof["workflow"], k, mmus, maxmem_threshold.ERROR_THRESHOLD)
            )

if errs > 0:
    exit(10)
