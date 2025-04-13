#!/usr/bin/env python3
import sys
from os.path import dirname, abspath

cmsbot_dir = None
if __file__:
    cmsbot_dir = dirname(dirname(abspath(__file__)))
else:
    cmsbot_dir = dirname(dirname(abspath(sys.argv[0])))
sys.path.insert(0, cmsbot_dir)

from es_utils import open_index

for i in sys.argv[1:]:
    open_index(i)
