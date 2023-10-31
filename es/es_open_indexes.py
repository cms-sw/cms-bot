#!/usr/bin/env python
from __future__ import print_function
import sys
from os.path import dirname, abspath

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, cmsbot_dir)

from es_utils import get_indexes, open_index, find_indexes
from time import time

cur_week = int(((time() / 86400) + 4) / 7)

for i in sys.argv[1:]:
    idxs = find_indexes(i)
    if not "close" in idxs:
        continue
    for ix in sorted(idxs["close"]):
        print("Opening ", ix)
        open_index(ix)
        print(get_indexes(ix))
