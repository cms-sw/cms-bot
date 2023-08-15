#!/usr/bin/env python3
from __future__ import print_function
from os.path import dirname, abspath
import sys

cmsbot_dir=None
if __file__: cmsbot_dir=dirname(dirname(abspath(__file__)))
else: cmsbot_dir=dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0,cmsbot_dir)

from es_utils import delete_index, find_indexes

for i in sys.argv[1:]:
  idxs = find_indexes(i)
  if not 'close' in idxs: continue
  for ix in sorted(idxs['close']):
    print("Deleting ", ix)
    delete_index(ix)
