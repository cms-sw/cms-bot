#!/usr/bin/python
from os.path import dirname, basename, abspath, join
import sys

cmsbot_dir=None
if __file__: cmsbot_dir=dirname(dirname(abspath(__file__)))
else: cmsbot_dir=dirname(dirname(abspath(argv[0])))
sys.path.insert(0,cmsbot_dir)

from es_utils import get_indexes, find_indexes
from time import time
cur_week=int(((time()/86400)+4)/7)

for i in sys.argv[1:]:
  idxs = find_indexes(i)
  for k in idxs:
    for ix in sorted(idxs[k]):
      print get_indexes(ix)

