#!/usr/bin/env python3
from __future__ import print_function
import sys
from os.path import dirname, abspath

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, cmsbot_dir)

from es_utils import get_indexes, find_indexes
from cmsutils import epoch2week
from time import time

cur_week = int(epoch2week(time(), 1))
print(sys.argv)
for i in sys.argv[1:]:
    idxs = find_indexes(i)
    for k in idxs:
        for ix in sorted(idxs[k]):
            print(get_indexes(ix))
