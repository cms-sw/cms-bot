#!/usr/bin/env python3
import json, sys, requests

gw   = sys.argv[1]
path = sys.argv[2].strip("/")
rep = requests.get(gw + '/leases')
data = rep.json()['data']
ecode = 1
for xentry in data.keys():
  entry = xentry.strip("/")
  rest = ""
  if entry.startswith(path):
    rest = entry[len(path):]
  elif path.startswith(entry):
    rest = path[len(entry):]
  else:
    continue
  print(rest)
  if rest and rest[0]!="/":
    continue
  ecode = 0
  print("Yes, there is lease for %s" % entry)
  print(data[xentry])
  break
sys.exit(ecode)
