#!/usr/bin/env python
from __future__ import print_function
from categories_map import CMSSW_CATEGORIES
import sys

pack2cat = {}
for cat in CMSSW_CATEGORIES:
    for pack in CMSSW_CATEGORIES[cat]:
        if pack not in pack2cat:
            pack2cat[pack] = []
        pack2cat[pack].append(cat)

files = {}
for f in sys.argv[1:]:
    file_pack = '/'.join(f.split('/')[:2])
    cat = 'unknown'
    if file_pack in pack2cat: cat = '-'.join(sorted(pack2cat[file_pack]))
    print('%s %s' % (cat, file_pack))
