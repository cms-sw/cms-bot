#!/usr/bin/env python
from __future__ import print_function

import sys
from os.path import abspath, dirname

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, cmsbot_dir)

from time import time

from es_utils import find_indexes, get_indexes

cur_week = int(((time() / 86400) + 4) / 7)

for i in sys.argv[1:]:
    idxs = find_indexes(i)
    for k in idxs:
        for ix in sorted(idxs[k]):
            print(get_indexes(ix))
