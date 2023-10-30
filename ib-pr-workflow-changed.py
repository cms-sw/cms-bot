#!/usr/bin/env python
from __future__ import print_function
import re
from sys import argv, exit
from _py2with3compatibility import run_cmd


def parse_workflows(workflow_file):
    err, out = run_cmd("cat %s" % workflow_file)
    if err:
        print(out)
        exit(1)

    wf = ""
    wfs = {}
    steps = 0
    for line in out.split("\n"):
        line = line.strip()
        m = re.match("^.*\[(\d+)\] *: *(.+)$", line)
        if not m:
            continue
        step = m.group(1)
        cmd = m.group(2).strip()
        prefix, rest = line.split(":", 1)
        items = prefix.split(" ")
        if re.match("^\d+(\.\d+|)$", items[0]):
            wf = items[0]
        if not wf in wfs:
            wfs[wf] = {}
        wfs[wf][step] = re.sub("  +", " ", cmd)
        steps += 1
    print("%s: %s workflows, %s steps" % (workflow_file, len(wfs), steps))
    return wfs


orig_workflows = argv[1]
new_workflows = argv[2]

wfs = {}
wfs["old"] = parse_workflows(argv[1])
wfs["new"] = parse_workflows(argv[2])

new_wf = []
new_step = []
chg_step = []
for wf in wfs["new"]:
    if not wf in wfs["old"]:
        new_wf.append(wf)
    else:
        for step in wfs["new"][wf]:
            if not step in wfs["old"][wf]:
                new_step.append(wf)
                break
            elif not wfs["old"][wf] == wfs["new"][wf]:
                chg_step.append(wf)
                break

print("New workflows:%s: %s" % (len(new_wf), ",".join(new_wf)))
print("Workflows with new steps:%s: %s" % (len(new_step), ",".join(new_step)))
print("Wrokflows with changed steps:%s: %s" % (len(chg_step), ",".join(chg_step)))
print("WORKFLOWS TO RUN:", ",".join(new_wf + new_step + chg_step))
