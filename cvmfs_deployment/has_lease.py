#!/usr/bin/env python3
import json, sys, requests

gw   = sys.argv[1]
path = sys.argv[2].strip("/")
rep = requests.get(gw + '/leases')
data = rep.json()['data']
for xentry in data.keys():
  entry = xentry.strip("/")
  rest = []
  if entry != path:
    if entry.startswith(path):
      rest = entry[len(path):]
    elif path.startswith(entry):
      rest = path[len(entry):]
    else:
      continue
  if (not rest) or (rest[0] == "/"):
    print("Yes, there is lease for %s" % entry)
    print(data[xentry])
    sys.exit(0)
sys.exit(1)
