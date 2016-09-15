#!/usr/bin/env python
from sys import argv, stdin
from CMSWeb import  CMSWeb 
cms=CMSWeb()

detail = False
cern   = False
for arg in argv:
  if arg=="--detail": detail=True
  elif arg=="--all": cern=True

for dataset in stdin:
  dataset = dataset.strip("\n")
  if not dataset: continue
  blocks = cms.search_blocks(dataset)
  min_bsize=999999999999999999999999999999
  bselected = []
  at_cern = False
  all_blocks = {}
  for block in blocks:
    bname = block['block_name']
    if cms.search_block(bname):
      bsize = cms.cache['blocks_raw'][bname]['phedex']['block'][0] ['bytes']/(1024*1024)
      all_blocks[bname]=[cms.cache["replicas"][bname].keys() , bsize]
      if cms.cache['blocks'][bname]['at_cern']=='yes':
         at_cern = True
         bselected = bname
      if bsize<min_bsize:
        min_bsize = bsize
        bselected = bname
  if not cern and at_cern: continue
  if detail: print all_blocks
  else: print bselected

