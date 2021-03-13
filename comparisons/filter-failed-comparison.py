#!/usr/bin/env python
from __future__ import print_function
import sys, glob
from os.path import basename,join
from os.path import dirname, abspath
sys.path.append(dirname(dirname(abspath(__file__))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

WF_PATH=sys.argv[1]
WF_DIR=basename(WF_PATH)
DES_DIR=join(sys.argv[2],WF_DIR)
for h in [basename(h)[:-5] for h in glob.glob(WF_PATH+"/*.html")]:
  e, o = run_cmd("grep 'Skipped:\|Null:\|Fail:' '%s/%s.html' | wc -l" % (WF_PATH,h))
  if (not e) and (int(o)>0):
    run_cmd("mv %s %s" % (WF_PATH, DES_DIR))
    run_cmd("echo ErrorDocument 404 /SDT/html/pr_comparison_ok.html > %s/.htaccess" % DES_DIR)
    break
print("Done filtering:", WF_DIR)
