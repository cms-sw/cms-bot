#!/usr/bin/env python3
from os import utime
from sys import exit
from os.path import isfile, islink
from subprocess import getstatusoutput as cmd
e, total =cmd("find . -type f | grep -v '/.git/' |wc -l")
e, o = cmd ('git log --name-only  --pretty=format:"T:%at"')
if e:
  print (o)
  exit(1)

cache = {}
time=0
cnt=0
for l in o.split("\n"):
  if not l: continue
  if l[:2]=='T:':
    time=int(l[2:])
    continue
  if l in cache: continue
  if isfile(l) and not islink(l):
    cnt += 1
    cache[l]=time
    utime(l, (time, time))
    print ("[%s/%s] %s: %s" % (cnt, total, l, time))
  else:
    cache[l]=0
