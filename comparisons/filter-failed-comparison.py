#!/usr/bin/env python
import sys, glob
from os.path import basename,join
if sys.version_info[0] == 2:
  from commands import getstatusoutput
else:
  from subprocess import getstatusoutput

WF_PATH=sys.argv[1]
WF_DIR=basename(WF_PATH)
DES_DIR=join(sys.argv[2],WF_DIR)

htmls=[basename(h)[:-5] for h in glob.glob(WF_PATH+"/*.html")]
all_ok=[]
DES_DIR_CREATED=False
for h in sorted(htmls):
  for s in all_ok[::-1]:
    if h.startswith(s):
      h = None
      break
  if not h: continue
  e, o = getstatusoutput("grep 'Skipped:\|Null:\|Fail:' '%s/%s.html' | wc -l" % (WF_PATH,h))
  if not e:
    if int(o)>0:
      if not DES_DIR_CREATED:
        getstatusoutput("mkdir -p %s" % DES_DIR)
        DES_DIR_CREATED=True
      getstatusoutput("mv '%s/%s.html' '%s/%s.html'" % (WF_PATH,h,DES_DIR,h))
    else:
      all_ok.append("%s_" % h)
  else:
    print("ERROR: %s/%s\n%s" %(WF_DIR,h,o))

if DES_DIR_CREATED:
  getstatusoutput("mv %s/*.png %s/" % (WF_PATH, DES_DIR))
  getstatusoutput("echo ErrorDocument 404 /SDT/html/pr_comparison_ok.html > %s/.htaccess" % DES_DIR)
print("DONE:", WF_DIR)
