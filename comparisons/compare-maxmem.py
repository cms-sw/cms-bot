#!/usr/bin/env python3
import sys
import json
from collections import defaultdict

def read_blocks(file):
    block = ''
    for line in file:
        if line.startswith("step") and len(block)>0:
            yield block
        else:
            block += line
    yield block

def create_memory_report(filename):
    memory_reports=list()
    step=0
    with open(filename, encoding="utf8", errors="ignore") as f:
        for block in read_blocks(f):
            step=step+1
            memory_report={}
            memory_report["step"]=step
            for line in block.split("\n"):
                if line.startswith("Memory Report:"):
                    fields=line.split(":")
                    memory_report[fields[1].strip()]=int(fields[2].strip())
            memory_reports.append(memory_report)
    return memory_reports


mem_prof_pr=create_memory_report(sys.argv[1])
mem_prof_base=create_memory_report(sys.argv[2])

print(json.dumps(mem_prof_pr))
#print()
print(json.dumps(mem_prof_base))
#print()
mem_keys=["step", "total memory requested",  "max memory used", "presently used", "# allocations calls", "# deallocations calls"]
#print("max memory pr")
#for key in mem_keys:
#    print(key, end=', ')
#print()
#for i in range(1, len(mem_prof_pr)): 
#    for key in mem_keys:
#        print(mem_prof_pr[i][key],end=', ')
#    print()
#print()
#print("max memory ib")
#for key in mem_keys:
#    print(key, end=', ')
#print()
#for i in range(1, len(mem_prof_base)): 
#    for key in mem_keys:
#        print(mem_prof_base[i][key], end=', ')
#    print()
#print()

#print("max memory percentage diffs")
#for key in mem_keys:
#    print(key, end=', ')
#print()
mem_prof_pdiffs=[]
for i in range(1, len(mem_prof_pr)):
    step=0
    mem_prof_pdiff={}
    for key in mem_keys:
        if key == "step":
#            print(mem_prof_pr[i][key], end=', ')
            step=mem_prof_pr[i][key]
            mem_prof_pdiff[key]=step
        else:
            diff=mem_prof_pr[i][key]-mem_prof_base[i][key]
            percent_diff=diff/mem_prof_pr[i][key]*100
#            print('%.2f' % percent_diff, end=', ')
            mem_prof_pdiff[key]=percent_diff
#    print()
    mem_prof_pdiffs.append(mem_prof_pdiff)
#print()

print(json.dumps(mem_prof_pdiffs))
#print("max memory absolute diffs")
#for key in mem_keys:
#    print(key, end=', ')
#print()
mem_prof_adiffs=[]
for i in range(1, len(mem_prof_pr)): 
    step=0
    mem_prof_adiff={}
    for key in mem_keys:
        if key == "step":
#            print(mem_prof_pr[i][key], end=', ')
            step=mem_prof_pr[i][key]
            mem_prof_adiff[key]=step
        else:
            diff=mem_prof_pr[i][key]-mem_prof_base[i][key]
#            print('%s' % diff, end=', ')
            mem_prof_adiff[key]=diff
#    print()
    mem_prof_adiffs.append(mem_prof_adiff)
#print()
print(json.dumps(mem_prof_adiffs))
