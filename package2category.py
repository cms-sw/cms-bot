#!/usr/bin/env python
from __future__ import print_function
from categories_map import CMSSW_CATEGORIES
import sys


def package2category(filename):
    if not filename:
        return
    file_pack = "/".join(filename.split("/")[:2])
    cat = "unknown"
    if file_pack in pack2cat:
        cat = "-".join(sorted(pack2cat[file_pack]))
    if not cat in cats:
        cats[cat] = {}
    cats[cat][file_pack] = 1


pack2cat = {}
for cat in CMSSW_CATEGORIES:
    for pack in CMSSW_CATEGORIES[cat]:
        if pack not in pack2cat:
            pack2cat[pack] = []
        pack2cat[pack].append(cat)

cats = {}
for line in sys.stdin:
    package2category(line.strip())

for line in sys.argv[1:]:
    package2category(line.strip())

for cat in cats:
    print("%s %s" % (cat, " ".join(cats[cat].keys())))
