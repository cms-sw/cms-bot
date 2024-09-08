#!/usr/bin/env python3
import sys
import json
from collections import defaultdict


def read_blocks(file):
    block = ""
    for line in file:
        if line.startswith("step") and len(block) > 0:
            yield block
        else:
            block += line
    yield block


def create_memory_report(filename):
    memory_reports = list()
    step = 0
    with open(filename, encoding="utf8", errors="ignore") as f:
        for block in read_blocks(f):
            if not block.find("Memory Report:") == -1:
                step = step + 1
                memory_report = {}
                memory_report["step"] = step
                for line in block.split("\n"):
                    if line.startswith("Memory Report:"):
                        fields = line.split(":")
                        memory_report[fields[1].strip()] = int(fields[2].strip())
                memory_reports.append(memory_report)
    return memory_reports


mem_prof_pr = create_memory_report(sys.argv[1])
mem_prof_base = create_memory_report(sys.argv[2])

mem_prof = {}

mem_prof["max memory pr"] = mem_prof_pr
mem_prof["max memory base"] = mem_prof_base

mem_keys = [
    "step",
    "total memory requested",
    "max memory used",
    "presently used",
    "# allocations calls",
    "# deallocations calls",
]
mem_prof_pdiffs = []
for i in range(0, len(mem_prof_pr)):
    step = 0
    mem_prof_pdiff = {}
    for key in mem_keys:
        if key == "step":
            step = mem_prof_pr[i][key]
            mem_prof_pdiff[key] = step
        else:
            mpp = mem_prof_pr[i].get(key)
            mpb = mem_prof_base[i].get(key)
            if mpp and mpb:
                diff = mpp - mpb
                percent_diff = diff / mpp * 100
                mem_prof_pdiff[key] = percent_diff
    mem_prof_pdiffs.append(mem_prof_pdiff)

mem_prof["max memory percentage diffs"] = mem_prof_pdiffs
sys.stdout.write("\n")

mem_prof_adiffs = []
for i in range(0, len(mem_prof_pr)):
    step = 0
    mem_prof_adiff = {}
    for key in mem_keys:
        if key == "step":
            step = mem_prof_pr[i][key]
            mem_prof_adiff[key] = step
        else:
            mpb = mem_prof_base[i].get(key)
            mpp = mem_prof_pr[i].get(key)
            if mpp and mpb:
                diff = mpp - mpb
                mem_prof_adiff[key] = diff
    mem_prof_adiffs.append(mem_prof_adiff)
mem_prof["max memory absolute diffs"] = mem_prof_adiffs

THREASHOLD = 1.0
mem_prof["threashold"] = THREASHOLD
sys.stdout.write(json.dumps(mem_prof))
sys.stdout.write("\n")

errs = 0
for i in range(0, len(mem_prof_pdiffs)):
    mmu = mem_prof_pdiffs[i].get("max memory used")
    if mmu:
        if abs(mmu) > THREASHOLD:
            errs = errs + 1
            sys.stderr.write(
                "step %s max memory used percentage diff %2f%% exceeds threashhold %2f%%"
                % (mem_prof_pdiffs[i]["step"], abs(mmu), THREASHOLD)
            )
            sys.stderr.write("\n")

if errs > 0:
    exit(10)
