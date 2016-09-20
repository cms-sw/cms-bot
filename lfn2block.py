#!/usr/bin/env python
from sys import argv, stdin
from CMSWeb import  CMSWeb 
cms=CMSWeb()

detail = False
cern   = False
for arg in argv:
  if arg=="--detail": detail=True
  elif arg=="--all": cern=True

blocks = {}
tsize = 0
for lfn in stdin:
  lfn = "/store/"+lfn.strip("\n").split("/store/")[-1]
  if not lfn: continue
  block = cms.search_lfn(lfn)
  if block:
    print block
    bname = block[0]['block_name']
    if not bname in blocks:
      blocks[bname]=1
      tsize = tsize + block[0]['block_size']

print "\n".join(blocks.keys())
print "Size (GB):",tsize/(1024*1024*1024)

