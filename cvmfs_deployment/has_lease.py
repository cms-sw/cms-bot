#!/usr/bin/env python3
import json, sys, requests

gw   = sys.argv[1]
path = sys.argv[2].strip("/")
rep = requests.get(gw + '/leases')
data = rep.json()['data']
for xentry in data.keys():
  entry = xentry.strip("/")
  rest = ""
  if entry != path:
    if entry.startswith(path):
      rest = entry[len(path):-1]
    elif path.startswith(entry):
      rest = path[len(entry):-1]
    else:
      continue
  if rest in ["", "/"]:
    print("Yes, there is lease for %s" % entry)
    print(data[xentry])
    sys.exit(0)
sys.exit(1)
