#!/usr/bin/env python
import sys
from commands import getstatusoutput
from pickle import Pickler

def doDu(what):
  error, out = getstatusoutput('du -k -s %s' % what)
  if error:
    print "Error while getting directory size."
    sys.exit(1)
  results = [l.split() for l in out.split("\n")]
  return dict([(pkg.strip().replace("src/", ''), int(sz.strip()*1024))
               for (sz, pkg) in results])

if __name__ == '__main__':
  try:
    f = open('dirSizeInfo.pkl', 'w')
    pklr = Pickler(f)
    pklr.dump(doDu("src lib bin"))
    pklr.dump(doDu("src/*/*"))
    f.close()
  except Exception, e:
    print "ERROR during pickling results for dir size:", str(e)
    sys.exit(1)
  print "Successfully pickled results for dir size !"
