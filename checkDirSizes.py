#!/usr/bin/env python3
from __future__ import print_function

import sys
from pickle import Pickler

from _py2with3compatibility import run_cmd


def doDu(what):
    error, out = run_cmd('du -k -s %s' % what)
    if error:
        print("Error while getting directory size.")
        sys.exit(1)
    results = [l.split() for l in out.split("\n")]
    return dict([(pkg.strip().replace("src/", ''), int(sz.strip() * 1024))
                 for (sz, pkg) in results])


if __name__ == '__main__':
    try:
        f = open('dirSizeInfo.pkl', 'wb')
        pklr = Pickler(f, protocol=2)
        pklr.dump(doDu("src lib bin"))
        pklr.dump(doDu("src/*/*"))
        f.close()
    except Exception as e:
        print("ERROR during pickling results for dir size:", str(e))
        sys.exit(1)
    print("Successfully pickled results for dir size !")
