#!/usr/bin/env python
from __future__ import print_function
import sys
import re

unknown = 0


def fix_file(line):
    global unknown
    m = re.match('^(\s*INSERT\s+INTO\s+files\s+VALUES\s+\((\d+),\s*["])([^"]*)(["].*$)', line)
    if m:
        xf = m.group(3)
        if xf:
            if xf[0] != "/":
                xf = "unknown-" + m.group(2)
        else:
            unknown += 1
            xf = "unknownfile-" + str(unknown)
        line = m.group(1) + xf + m.group(4)
    return line


xline = ""
for line in open(sys.argv[1]).readlines():
    line = line.strip("\n")
    if xline:
        xline = xline + line
        if line.endswith(");"):
            line = fix_file(xline)
            xline = ""
        else:
            continue
    elif line.startswith("INSERT INTO files"):
        if not line.endswith(");"):
            xline = line
            continue
        else:
            line = fix_file(line)
    print(line)
