#!/bin/env python
from __future__ import print_function
import sys, json

fd = open(sys.argv[1], "r")
info = {}
includes = 0
excludes = 0
pkg_name = "/".join(sys.argv[1].split("/")[-3:-1])
files = 0
splitline = sys.argv[2] + "/src/"
print(
    """<!DOCTYPE html>
<html>
<head>
<style>
table, th, td {
    border: 2px solid green;
    border-collapse: collapse;
}
th, td {
    padding: 5px;
    text-align: left;
}
</style>
</head>"""
)
print("<a href=" + '"' + sys.argv[1].split("/")[-1] + '"' + ">" + "Access BuildLog" + "</a><br/>")
print('<table  align="center">')
lines_seen = set()
for l in fd:
    if "remove these lines" in l and l not in lines_seen:
        lines_seen.add(l)
        sec = iter(fd)
        line = next(sec)
        line = line.rstrip()
        if len(line):
            files += 1
            items = l.split(splitline)[-1].split(" ", 1)
            print(
                '<tr><td bgcolor="#00FFFF"><b><a href='
                + '"'
                + "https://github.com/cms-sw/cmssw/tree/"
                + sys.argv[2]
                + "/"
                + items[0]
                + '"'
                + ">"
                + items[0]
                + "</a> "
                + items[1]
                + "</b>"
            )
            while len(line):
                excludes += 1
                line = line.replace("<", "&#60;")
                line = line.replace(">", "&#62;")
                print("<br/>" + line)
                line = next(sec)
                line = line.rstrip()
            print("</td></tr>")

    elif "add these lines" in l and l not in lines_seen:
        lines_seen.add(l)
        sec = iter(fd)
        line = next(sec)
        line = line.rstrip()
        if len(line):
            files += 1
            items = l.split(splitline)[-1].split(" ", 1)
            print(
                '<tr><td bgcolor="#00FF90"><b><a href='
                + '"'
                + "https://github.com/cms-sw/cmssw/tree/"
                + sys.argv[2]
                + "/"
                + items[0]
                + '"'
                + ">"
                + items[0]
                + "</a> "
                + items[1]
                + "</b>"
            )
            while len(line):
                includes += 1
                line = line.replace("<", "&#60;")
                line = line.replace(">", "&#62;")
                print("<br />" + line)
                line = next(sec)
                line = line.rstrip()
            print("</td></tr>")
print("</table>")
stat = [files, includes, excludes]
info[pkg_name] = stat
output_file = open("stats.json", "a")
output_file.write(json.dumps(info))
output_file.close()
