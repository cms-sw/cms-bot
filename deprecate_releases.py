#!/bin/env python
from __future__ import print_function
import sys
if len(sys.argv) < 3:
  print("Usage: %s releases.map cmssw_version [cmssw_version [...]]" % sys.argv[0]) 
  sys.exit(1)

release_map = sys.argv[1]
deprecate_list = sys.argv[2:]
fd = open(release_map,'r')
for line in fd.readlines():
  release = line.split(';label=',1)[1].split(";",1)[0] 
  if release in deprecate_list:
    line = line.replace('Announced','Deprecated')
  print(line, end=' ')    
