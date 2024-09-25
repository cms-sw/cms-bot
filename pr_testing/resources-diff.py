#! /usr/bin/env python3

import sys
import json

def diff_from(metrics, data, dest):
  dest["events"] -= data["events"]
  for metric in metrics:
    dest[metric] -= data[metric]

if (len(sys.argv) == 1):
  print("""Usage: diff.py FILE [FILE ...]
Diff the content of two "resources.json" files and print the result to standard output.""")
  sys.exit(1)

with open(sys.argv[1]) as f:
  output = json.load(f)

metrics = [ label for resource in output["resources"] for label in resource ]

datamap = { module["type"] + '|' + module["label"] : module for module in output["modules"] }

for arg in sys.argv[2:]:
  with open(arg) as f:
    input = json.load(f)

  if output["resources"] != input["resources"]:
    print("Error: input files describe different metrics")
    sys.exit(1)

  if output["total"]["label"] != input["total"]["label"]:
    print("Warning: input files describe different process names")
  diff_from(metrics, input["total"], output["total"])

  for module in input["modules"]:
    key = module["type"] + '|' + module["label"]
    if key in datamap:
      diff_from(metrics, module, datamap[key])
    else:
      datamap[key] = module
      output["modules"].append(datamap[key])

json.dump(output, sys.stdout, indent = 2 )
sys.stdout.write('\n')
