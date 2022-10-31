#!/usr/bin/env python3
import json, sys, requests

gw   = sys.argv[1]
path = sys.argv[2].strip("/")
rep = requests.get(gw + '/leases')
data = rep.json()['data']
for entry in [e.strip("/") for e in data.keys()]:
  rest = None
  if entry.startswith(path):
    rest = entry[len(path):]
  elif path.startswith(entry):
    rest = path[len(entry):]
  else:
    continue
  if (not rest) or (rest[0] == "/"):
    print("Yes, there is lease for %s" % entry)
    print(data[entry])
    sys.exit(0)
sys.exit(1)

