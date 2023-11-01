#!/usr/bin/env python
from __future__ import print_function
import sys

# run this command for once to create the data file or directly pipe its output to this script
# for releases
# find /afs/cern.ch/cms/slc[5-7]* -maxdepth 3 -type d -print -exec fs lq {} \; | grep -v 'Volume Name' | sed 'N;s/\n/ /' | uniq -c -f2
# for ibs
# find /afs/cern.ch/cms/sw/ReleaseCandidates/ -maxdepth 3 -type d -print -exec fs lq {} \; |grep -v '^Volume' | sed 'N;s/\n/ /' | uniq -c -f3

data = {}
allocated = 0
used = 0
volumes = 0
max_volume_len = 0
max_path_len = 0
for line in sys.stdin:
    info = line.strip().split()
    if info[2] in data:
        continue
    volumes += 1
    allocated = allocated + int(info[3])
    used = used + int(info[4])
    data[info[2]] = info
    if len(info[2]) > max_volume_len:
        max_volume_len = len(info[2])
    if len(info[1]) > max_path_len:
        max_path_len = len(info[1])
max_volume_len = max_volume_len + 4
max_path_len = max_path_len + 4

print("Total Volumes  :", volumes)
print("Allocated Space:", int(allocated / 1000000), "GB")
print("Used Space     :", int(used / 1000000), "GB")
for vol in sorted(data):
    msg = "{0:<" + str(max_volume_len) + "}{1:<" + str(max_path_len) + "}"
    print(msg.format(vol, data[vol][1]), data[vol][4] + "/" + data[vol][3])
