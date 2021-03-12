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

htmls=[basename(h)[:-5] for h in glob.glob(WF_PATH+"/*.html")]
DES_DIR_CREATED=False
for h in sorted(htmls):
  e, o = run_cmd("grep 'Skipped:\|Null:\|Fail:' '%s/%s.html' | wc -l" % (WF_PATH,h))
  if not e:
    if int(o)>0:
      if not DES_DIR_CREATED:
        print("Found errors %s/%s" %  (WF_PATH,h))
        run_cmd("mkdir -p %s" % DES_DIR)
        DES_DIR_CREATED=True
      run_cmd("mv '%s/%s.html' '%s/%s.html'" % (WF_PATH,h,DES_DIR,h))
  else:
    print("Error Filtering: %s/%s\n%s" %(WF_DIR,h,o))

if DES_DIR_CREATED:
  e, o = run_cmd("mv %s/*.png %s/" % (WF_PATH, DES_DIR))
  print("Copy png: %s" % o)
  run_cmd("echo ErrorDocument 404 /SDT/html/pr_comparison_ok.html > %s/.htaccess" % DES_DIR)
print("Done filtering:", WF_DIR)
